"""transcribe.py の WhisperX 連動部分のテスト。

実 WhisperX は重い+モデル DL が走るので、`whisperx` モジュールを
スタブ化して `_load_model` の引数受け渡しだけを検証する。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config


def _mk_cfg(tmp_path: Path, *, prompt_file: Path | None = None) -> Config:
    vault = tmp_path / "vault"
    return Config(
        jpr_inbox=tmp_path / "jpr",
        vault=vault,
        transcripts_dir=vault / "_transcripts",
        notes_dir=vault / "録音",
        skip_duration_s=10,
        skip_silence_ratio=0.95,
        skip_silence_db=-40,
        whisper_model="large-v3-turbo",
        whisper_device="cpu",
        whisper_compute_type="int8",
        whisper_language="ja",
        whisper_initial_prompt_path=prompt_file,
        whisper_align_enabled=False,
        file_stable_wait_s=5,
        file_stable_poll_s=2,
        anthropic_api_key="",
        anthropic_model="claude-opus-4-7",
        anthropic_max_tokens=8192,
        anthropic_effort="medium",
        structuring_prompt_path=None,
    )


def _install_whisperx_stub(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    """`import whisperx` を stub に差し替える。load_model の引数を captured に記録。"""
    stub = types.ModuleType("whisperx")

    def fake_load_model(name, **kwargs):
        captured["name"] = name
        captured["kwargs"] = kwargs
        return object()

    stub.load_model = fake_load_model
    monkeypatch.setitem(sys.modules, "whisperx", stub)


def test_load_model_passes_initial_prompt_via_asr_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """initial_prompt が asr_options={"initial_prompt": ...} で渡されること。"""
    prompt_file = tmp_path / "initial.txt"
    prompt_file.write_text("浦安市 市民スポーツ課 モルック", encoding="utf-8")
    cfg = _mk_cfg(tmp_path, prompt_file=prompt_file)

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()  # 他テストとの汚染防止
    transcribe._load_model(cfg)

    assert captured["name"] == "large-v3-turbo"
    kwargs = captured["kwargs"]
    assert kwargs["device"] == "cpu"
    assert kwargs["compute_type"] == "int8"
    assert kwargs["language"] == "ja"
    assert kwargs["asr_options"] == {
        "initial_prompt": "浦安市 市民スポーツ課 モルック"
    }


def test_load_model_omits_asr_options_when_no_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """initial_prompt 未設定なら asr_options 自体を渡さない
    (WhisperX のデフォルトに従わせる)。"""
    cfg = _mk_cfg(tmp_path, prompt_file=None)

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    assert "asr_options" not in captured["kwargs"]


def test_load_model_omits_asr_options_when_prompt_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """設定はされてるがファイルが無い場合も asr_options を渡さない。"""
    cfg = _mk_cfg(tmp_path, prompt_file=tmp_path / "ghost.txt")

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    assert "asr_options" not in captured["kwargs"]


def test_load_model_omits_asr_options_when_prompt_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ファイルはあるが空文字なら asr_options を渡さない。"""
    prompt_file = tmp_path / "initial.txt"
    prompt_file.write_text("   \n\n  ", encoding="utf-8")  # whitespace only
    cfg = _mk_cfg(tmp_path, prompt_file=prompt_file)

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    assert "asr_options" not in captured["kwargs"]


def test_load_model_caches_within_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """同じ cfg で2回呼ばれた時、load_model は1回しか呼ばれない。"""
    cfg = _mk_cfg(tmp_path)

    call_count = {"n": 0}
    stub = types.ModuleType("whisperx")

    def fake_load_model(name, **kwargs):
        call_count["n"] += 1
        return object()

    stub.load_model = fake_load_model
    monkeypatch.setitem(sys.modules, "whisperx", stub)

    import transcribe

    transcribe._model_cache.clear()
    m1 = transcribe._load_model(cfg)
    m2 = transcribe._load_model(cfg)

    assert m1 is m2
    assert call_count["n"] == 1
