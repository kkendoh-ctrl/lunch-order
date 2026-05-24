"""structure.py の純粋関数テスト(Claude API 呼び出しなし)。"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import structure
from config import Config


def test_extract_json_plain() -> None:
    raw = '{"date": "2026-05-23", "contexts": []}'
    assert structure._extract_json(raw) == {
        "date": "2026-05-23",
        "contexts": [],
    }


def test_extract_json_with_fence() -> None:
    raw = "```json\n" + '{"a": 1}' + "\n```"
    assert structure._extract_json(raw) == {"a": 1}


def test_extract_json_with_preamble() -> None:
    raw = "こちらが結果です:\n```json\n" + '{"a": 1, "b": [2, 3]}' + "\n```\n以上。"
    assert structure._extract_json(raw) == {"a": 1, "b": [2, 3]}


def test_extract_json_braces_only() -> None:
    raw = 'noise {"x": "y"} more noise'
    assert structure._extract_json(raw) == {"x": "y"}


def test_extract_json_raises_on_garbage() -> None:
    with pytest.raises(ValueError):
        structure._extract_json("これは JSON ではない普通の文章です")


# -------------------- _markdown_to_fallback_structured --------------------


def test_markdown_fallback_extracts_h1_title() -> None:
    md = (
        "# 構造化メモ: test_5min\n"
        "## ⚠️ 文字起こし品質に関する注意\n"
        "本録音は ASR 品質が低い。\n"
    )
    result = structure._markdown_to_fallback_structured(md)
    ctxs = result["contexts"]
    assert len(ctxs) == 1
    assert ctxs[0]["title"] == "構造化メモ: test_5min"


def test_markdown_fallback_default_title_when_no_h1() -> None:
    md = "## 要旨\n本文だけ。\n"
    result = structure._markdown_to_fallback_structured(md)
    assert result["contexts"][0]["title"].startswith("構造化失敗")


def test_markdown_fallback_preserves_original_in_summary() -> None:
    md = "# Title\n\n## セクション\n中身。"
    result = structure._markdown_to_fallback_structured(md)
    summary = result["contexts"][0]["summary"]
    assert "中身。" in summary
    assert "手動レビュー" in summary  # 警告メッセージが先頭


def test_markdown_fallback_truncates_long_input() -> None:
    md = "# Title\n\n" + ("あ" * 5000)
    result = structure._markdown_to_fallback_structured(md)
    summary = result["contexts"][0]["summary"]
    # 4000 で切れ + 警告メッセージ分は超えるが原文部分は ~4000 で truncate
    assert "以下省略" in summary


def test_markdown_fallback_marks_with_review_domain() -> None:
    md = "# x"
    result = structure._markdown_to_fallback_structured(md)
    ctx = result["contexts"][0]
    assert ctx["domains"] == ["要レビュー"]
    assert ctx["importance"] == 2
    # note_writer が期待するキーは全部存在
    for key in (
        "counterpart",
        "topics",
        "locations",
        "todos",
        "key_points",
        "open_questions",
        "summary",
        "sentiment",
    ):
        assert key in ctx


def test_split_prompt_extracts_fence_content() -> None:
    template = """# Header

説明文。

```
あなたは音声記憶アシスタントです。

## 入力
{{TRANSCRIPT}}
```

補足
"""
    system = structure._split_prompt(template)
    assert "あなたは音声記憶アシスタント" in system
    assert "{{TRANSCRIPT}}" not in system


def test_split_prompt_no_fence() -> None:
    template = "プレーンなプロンプト本文。 {{TRANSCRIPT}} 末尾。"
    system = structure._split_prompt(template)
    assert system == "プレーンなプロンプト本文。"
    assert "TRANSCRIPT" not in system


def test_format_transcript_for_user() -> None:
    transcript = {
        "date": "2026-05-23",
        "time": "13:39:19",
        "duration_s": 12.5,
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "こんにちは"},
            {"start": 65.0, "end": 70.0, "text": "1分過ぎ"},
        ],
    }
    text = structure._format_transcript_for_user(transcript)
    assert "録音日時: 2026-05-23 13:39:19" in text
    assert "長さ: 12.5 秒" in text
    assert "[00:00] こんにちは" in text
    assert "[01:05] 1分過ぎ" in text


def test_enrich_transcript_meta_from_audio_path() -> None:
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    enriched = structure._enrich_transcript_meta({}, audio)
    assert enriched["date"] == "2026-05-23"
    assert enriched["time"] == "13:39:19"


def test_enrich_transcript_meta_preserves_existing() -> None:
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    enriched = structure._enrich_transcript_meta(
        {"date": "override", "time": "11:11:11"}, audio
    )
    assert enriched["date"] == "override"
    assert enriched["time"] == "11:11:11"


# -------------------- Phase 4: PII マスキング統合 --------------------


def _tool_use_block(input_data: dict, name: str = "save_structured_memo"):
    return types.SimpleNamespace(type="tool_use", name=name, input=input_data)


def _text_block(text: str):
    return types.SimpleNamespace(type="text", text=text)


class _StubResponse:
    """anthropic SDK の messages.create が返すレスポンスの最小スタブ。"""

    def __init__(
        self, *, content: list | None = None, text: str | None = None
    ) -> None:
        if content is not None:
            self.content = content
        elif text is not None:
            self.content = [_text_block(text)]
        else:
            self.content = []
        self.stop_reason = "end_turn"
        self.model = "claude-opus-4-7"
        self.usage = types.SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )


class _StubStream:
    """Anthropic SDK の `client.messages.stream(...)` が返すコンテキスト
    マネージャの最小スタブ。`get_final_message()` で固定 Response を返す。"""

    def __init__(self, response: _StubResponse) -> None:
        self._response = response

    def __enter__(self) -> "_StubStream":
        return self

    def __exit__(self, *args) -> None:
        return None

    def get_final_message(self) -> _StubResponse:
        return self._response


class _StubMessages:
    def __init__(self, captured: dict, response_factory) -> None:
        self.captured = captured
        self._response_factory = response_factory

    def stream(self, **kwargs) -> _StubStream:
        self.captured.update(kwargs)
        return _StubStream(self._response_factory())


class _StubClient:
    def __init__(self, api_key: str, captured: dict, response_factory) -> None:
        self.messages = _StubMessages(captured, response_factory)


def _mk_cfg(tmp_path: Path, *, pii_enabled: bool, dict_path: Path | None) -> Config:
    vault = tmp_path / "vault"
    return Config(
        jpr_inbox=tmp_path / "jpr",
        vault=vault,
        transcripts_dir=vault / "_transcripts",
        notes_dir=vault / "録音",
        skip_duration_s=10,
        skip_silence_ratio=0.95,
        skip_silence_db=-40,
        whisper_model="large-v3",
        whisper_device="cpu",
        whisper_compute_type="int8",
        whisper_language="ja",
        whisper_initial_prompt_path=None,
        whisper_align_enabled=False,
        file_stable_wait_s=5,
        file_stable_poll_s=2,
        anthropic_api_key="dummy",
        anthropic_model="claude-opus-4-7",
        anthropic_max_tokens=8192,
        anthropic_effort="medium",
        structuring_prompt_path=None,
        pii_mask_enabled=pii_enabled,
        pii_dict_path=dict_path,
        pii_allowlist_path=None,
    )


def _install_anthropic_stub(
    monkeypatch, captured: dict, response_factory=None
) -> None:
    """import anthropic を Stub に差し替える。

    response_factory は引数なしで _StubResponse を返す callable。
    省略時は contexts=[] の tool_use ブロックを返す(従来挙動の代替)。"""
    if response_factory is None:
        def response_factory():  # noqa: E306
            return _StubResponse(
                content=[_tool_use_block({"contexts": []})]
            )
    stub_module = types.ModuleType("anthropic")
    stub_module.Anthropic = lambda api_key: _StubClient(
        api_key, captured, response_factory
    )
    monkeypatch.setitem(sys.modules, "anthropic", stub_module)


def test_structure_transcript_masks_before_send(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Claude に送る user_content がマスク済みなことを確認。"""
    dict_path = tmp_path / "pii.yaml"
    dict_path.write_text("田中花子: '[個人A]'\n", encoding="utf-8")
    cfg = _mk_cfg(tmp_path, pii_enabled=True, dict_path=dict_path)

    captured: dict = {}
    _install_anthropic_stub(monkeypatch, captured)

    transcript = {
        "duration_s": 10.0,
        "segments": [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "田中花子さん 090-1234-5678 から連絡",
            }
        ],
        "text": "田中花子さん 090-1234-5678 から連絡",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    result = structure.structure_transcript(transcript, audio, cfg)

    # Claude に送られた user_content にマスク後のテキストが含まれる
    messages = captured["messages"]
    sent_text = messages[0]["content"]
    assert "[個人A]" in sent_text
    assert "[電話番号]" in sent_text
    assert "田中花子" not in sent_text
    assert "090-1234-5678" not in sent_text

    # pii_masked が結果に含まれる
    # 1 segment text + 1 連結 text の各々で 2 件ずつ = 4
    assert result["pii_masked"] == 4


def test_structure_transcript_skips_masking_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}
    _install_anthropic_stub(monkeypatch, captured)

    transcript = {
        "duration_s": 5.0,
        "segments": [{"start": 0.0, "end": 3.0, "text": "090-1234-5678 です"}],
        "text": "090-1234-5678 です",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    result = structure.structure_transcript(transcript, audio, cfg)

    sent_text = captured["messages"][0]["content"]
    # マスクされずに残っている
    assert "090-1234-5678" in sent_text
    assert "[電話番号]" not in sent_text
    assert result["pii_masked"] == 0


# -------------------- tool_use 経路 --------------------


def test_structure_transcript_forces_tool_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """messages.create に tools と tool_choice 強制が渡ること。"""
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}
    _install_anthropic_stub(monkeypatch, captured)

    transcript = {
        "duration_s": 5.0,
        "segments": [{"start": 0.0, "end": 3.0, "text": "テスト"}],
        "text": "テスト",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    structure.structure_transcript(transcript, audio, cfg)

    # tools パラメータが渡されている
    tools = captured["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "save_structured_memo"
    schema = tools[0]["input_schema"]
    assert schema["properties"]["contexts"]["type"] == "array"
    ctx_props = schema["properties"]["contexts"]["items"]["properties"]
    # note_writer/aggregator が必要とするキーが全部 schema にある
    for key in (
        "title",
        "summary",
        "importance",
        "counterpart",
        "topics",
        "locations",
        "domains",
        "sentiment",
        "todos",
        "key_points",
        "open_questions",
    ):
        assert key in ctx_props, f"schema に {key} が無い"

    # tool_choice は特定ツール指定で save_structured_memo を強制呼出。
    assert captured["tool_choice"] == {
        "type": "tool",
        "name": "save_structured_memo",
    }
    # Anthropic API は tool_choice 強制と thinking の併用を拒否するため
    # (400: "Thinking may not be enabled when tool_choice forces tool use.")、
    # thinking / output_config は messages.create に渡さない。
    assert "thinking" not in captured
    assert "output_config" not in captured


def test_structure_transcript_parses_tool_use_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """tool_use ブロックの input がそのまま structured として返ること。"""
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}

    tool_input = {
        "date": "2026-05-23",
        "time": "13:39:19",
        "duration_s": 12.5,
        "contexts": [
            {
                "title": "モルック大会の打合せ",
                "summary": "総合体育館で開催。",
                "importance": 4,
                "counterpart": ["田中さん"],
                "topics": ["モルック大会"],
                "locations": ["総合体育館"],
                "domains": ["業務", "私的"],
                "sentiment": "ニュートラル",
                "todos": [
                    {"text": "見積もり確認", "due": "2026-05-30", "assignee": "self"}
                ],
                "key_points": ["参加費は無料"],
                "open_questions": ["駐車場の有無"],
            }
        ],
    }

    def factory():
        return _StubResponse(content=[_tool_use_block(tool_input)])

    _install_anthropic_stub(monkeypatch, captured, factory)

    transcript = {
        "duration_s": 12.5,
        "segments": [{"start": 0.0, "end": 12.5, "text": "..."}],
        "text": "...",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    result = structure.structure_transcript(transcript, audio, cfg)

    assert result["structuring_format"] == "tool_use"
    assert result["structured"] == tool_input
    # ノート生成側で必要なキーが入っていることを確認
    assert result["structured"]["contexts"][0]["title"] == "モルック大会の打合せ"


def test_structure_transcript_empty_contexts_tool_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """雑談判定で contexts=[] が tool_use で返ってきても正しく扱える。"""
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}

    def factory():
        return _StubResponse(content=[_tool_use_block({"contexts": []})])

    _install_anthropic_stub(monkeypatch, captured, factory)

    transcript = {
        "duration_s": 5.0,
        "segments": [{"start": 0.0, "end": 5.0, "text": "あー"}],
        "text": "あー",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    result = structure.structure_transcript(transcript, audio, cfg)

    assert result["structuring_format"] == "tool_use"
    assert result["structured"] == {"contexts": []}


def test_structure_transcript_falls_back_to_text_when_no_tool_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """tool_use ブロックが無く JSON text が返ったケース(レア)。
    旧 _extract_json 経路で拾えるので structuring_format=json。"""
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}

    def factory():
        return _StubResponse(text='{"contexts": [{"title": "t", "summary": "s", "importance": 3}]}')

    _install_anthropic_stub(monkeypatch, captured, factory)

    transcript = {
        "duration_s": 5.0,
        "segments": [{"start": 0.0, "end": 5.0, "text": "テスト"}],
        "text": "テスト",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    result = structure.structure_transcript(transcript, audio, cfg)

    assert result["structuring_format"] == "json"
    assert result["structured"]["contexts"][0]["title"] == "t"


def test_structure_transcript_falls_back_to_markdown_when_no_tool_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """tool_use も JSON も無く Markdown が返ったレアケース。
    既存の markdown_fallback がそのまま機能する。"""
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}

    def factory():
        return _StubResponse(text="# Markdown レポート\n本文")

    _install_anthropic_stub(monkeypatch, captured, factory)

    transcript = {
        "duration_s": 5.0,
        "segments": [{"start": 0.0, "end": 5.0, "text": "テスト"}],
        "text": "テスト",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    result = structure.structure_transcript(transcript, audio, cfg)

    assert result["structuring_format"] == "markdown_fallback"
    assert "Markdown レポート" in result["structured"]["contexts"][0]["summary"]


def test_structure_transcript_raises_when_response_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """tool_use も text も無いレスポンスは RuntimeError で落とす(運用安全)。"""
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}

    def factory():
        return _StubResponse(content=[])

    _install_anthropic_stub(monkeypatch, captured, factory)

    transcript = {
        "duration_s": 5.0,
        "segments": [{"start": 0.0, "end": 5.0, "text": "テスト"}],
        "text": "テスト",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    with pytest.raises(RuntimeError):
        structure.structure_transcript(transcript, audio, cfg)


# -------------------- tool schema 自体 --------------------


# -------------------- streaming / max_tokens 警告 (応答 #16) --------------------


def test_structure_transcript_uses_streaming_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """messages.stream(...) が呼ばれること (create ではなく)。"""
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}

    def factory():
        return _StubResponse(content=[_tool_use_block({"contexts": []})])

    _install_anthropic_stub(monkeypatch, captured, factory)

    transcript = {
        "duration_s": 5.0,
        "segments": [{"start": 0.0, "end": 5.0, "text": "テスト"}],
        "text": "テスト",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    # ここで例外が出なければ stream() が正しく呼ばれている (stub に create() は無い)
    result = structure.structure_transcript(transcript, audio, cfg)
    assert result["structuring_format"] == "tool_use"
    # captured に messages.stream() の引数が入っている
    assert "messages" in captured
    assert "tools" in captured


def test_structure_transcript_warns_when_max_tokens_exhausted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """out_tokens == max_tokens のとき警告が stdout に出る。"""
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}

    def factory():
        # max_tokens=8192 ちょうど使い切ったケースをシミュレート
        resp = _StubResponse(content=[_tool_use_block({"contexts": []})])
        resp.usage = types.SimpleNamespace(
            input_tokens=100,
            output_tokens=8192,  # max_tokens にちょうど一致
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        return resp

    _install_anthropic_stub(monkeypatch, captured, factory)

    cfg_low = Config(**{**cfg.__dict__, "anthropic_max_tokens": 8192})
    transcript = {
        "duration_s": 5.0,
        "segments": [{"start": 0.0, "end": 5.0, "text": "テスト"}],
        "text": "テスト",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    structure.structure_transcript(transcript, audio, cfg_low)

    out = capsys.readouterr().out
    assert "max_tokens=8192" in out
    assert "使い切り" in out
    assert "out=8192" in out


def test_structure_transcript_no_warn_below_max_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """out_tokens < max_tokens なら警告無し。"""
    cfg = _mk_cfg(tmp_path, pii_enabled=False, dict_path=None)
    captured: dict = {}
    _install_anthropic_stub(monkeypatch, captured)  # default = output_tokens=50

    transcript = {
        "duration_s": 5.0,
        "segments": [{"start": 0.0, "end": 5.0, "text": "テスト"}],
        "text": "テスト",
    }
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    structure.structure_transcript(transcript, audio, cfg)

    out = capsys.readouterr().out
    assert "使い切り" not in out


# -------------------- tool schema 自体 --------------------


def test_structured_tool_schema_well_formed() -> None:
    schema = structure._structured_tool_schema()
    assert schema["name"] == "save_structured_memo"
    assert "input_schema" in schema
    root = schema["input_schema"]
    assert root["type"] == "object"
    assert root["required"] == ["contexts"]
    # contexts items の必須キー
    ctx = root["properties"]["contexts"]["items"]
    assert set(ctx["required"]) == {"title", "summary", "importance"}
    # importance は 1..5 の整数
    imp = ctx["properties"]["importance"]
    assert imp["type"] == "integer"
    assert imp["minimum"] == 1
    assert imp["maximum"] == 5
