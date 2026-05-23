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


class _StubResponse:
    """anthropic SDK の messages.create が返すレスポンスの最小スタブ。"""

    def __init__(self, text: str) -> None:
        self.content = [types.SimpleNamespace(type="text", text=text)]
        self.stop_reason = "end_turn"
        self.model = "claude-opus-4-7"
        self.usage = types.SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )


class _StubMessages:
    def __init__(self, captured: dict) -> None:
        self.captured = captured

    def create(self, **kwargs) -> _StubResponse:
        self.captured.update(kwargs)
        return _StubResponse('{"contexts": []}')


class _StubClient:
    def __init__(self, api_key: str, captured: dict) -> None:
        self.messages = _StubMessages(captured)


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


def _install_anthropic_stub(monkeypatch, captured: dict) -> None:
    """import anthropic を Stub に差し替える。"""
    stub_module = types.ModuleType("anthropic")
    stub_module.Anthropic = lambda api_key: _StubClient(api_key, captured)
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
