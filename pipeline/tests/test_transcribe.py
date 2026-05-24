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


def _mk_cfg(
    tmp_path: Path,
    *,
    prompt_file: Path | None = None,
    vad_method: str = "pyannote",
    condition_on_previous_text: bool = False,
    temperatures: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
    hallucination_silence_threshold: float = 0.0,
) -> Config:
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
        whisper_vad_method=vad_method,
        whisper_condition_on_previous_text=condition_on_previous_text,
        whisper_temperatures=temperatures,
        whisper_compression_ratio_threshold=2.4,
        whisper_log_prob_threshold=-1.0,
        whisper_no_speech_threshold=0.6,
        whisper_repetition_penalty=1.1,
        whisper_hallucination_silence_threshold=hallucination_silence_threshold,
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


_BASE_HALLUCINATION_KEYS = {
    "temperatures",
    "compression_ratio_threshold",
    "log_prob_threshold",
    "no_speech_threshold",
    "repetition_penalty",
    "condition_on_previous_text",
}


def test_load_model_passes_initial_prompt_via_asr_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """initial_prompt が asr_options 経由で渡されること。
    ハルシネーション抑止スタックも常時同居する。"""
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
    asr = kwargs["asr_options"]
    assert asr["initial_prompt"] == "浦安市 市民スポーツ課 モルック"
    assert asr["condition_on_previous_text"] is False
    assert asr["temperatures"] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    assert asr["repetition_penalty"] == 1.1


def test_load_model_default_hallucination_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """initial_prompt 未設定でも、ハルシネーション抑止スタックは常時渡る。"""
    cfg = _mk_cfg(tmp_path, prompt_file=None)

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    asr = captured["kwargs"]["asr_options"]
    assert set(asr.keys()) == _BASE_HALLUCINATION_KEYS
    assert asr["temperatures"] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    assert asr["compression_ratio_threshold"] == 2.4
    assert asr["log_prob_threshold"] == -1.0
    assert asr["no_speech_threshold"] == 0.6
    assert asr["repetition_penalty"] == 1.1
    assert asr["condition_on_previous_text"] is False
    # hallucination_silence_threshold は 0 のとき入れない
    assert "hallucination_silence_threshold" not in asr


def test_load_model_can_opt_in_condition_on_previous_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WHISPER_CONDITION_ON_PREVIOUS_TEXT=true 相当の設定で旧挙動に戻せる。
    その場合 condition_on_previous_text キーは asr_options に入らない
    (WhisperX/FW のデフォルト True を採用)。"""
    cfg = _mk_cfg(tmp_path, prompt_file=None, condition_on_previous_text=True)

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    asr = captured["kwargs"]["asr_options"]
    assert "condition_on_previous_text" not in asr
    # 他のハルシネーション抑止キーは残る
    assert "temperatures" in asr
    assert "repetition_penalty" in asr


def test_load_model_omits_initial_prompt_when_prompt_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ファイル無し → initial_prompt は asr_options に入らない
    (ハルシネーション抑止キーは入る)。"""
    cfg = _mk_cfg(tmp_path, prompt_file=tmp_path / "ghost.txt")

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    asr = captured["kwargs"]["asr_options"]
    assert "initial_prompt" not in asr
    assert set(asr.keys()) == _BASE_HALLUCINATION_KEYS


def test_load_model_omits_initial_prompt_when_prompt_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ファイルはあるが空文字 → initial_prompt は入らない。"""
    prompt_file = tmp_path / "initial.txt"
    prompt_file.write_text("   \n\n  ", encoding="utf-8")  # whitespace only
    cfg = _mk_cfg(tmp_path, prompt_file=prompt_file)

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    asr = captured["kwargs"]["asr_options"]
    assert "initial_prompt" not in asr
    assert set(asr.keys()) == _BASE_HALLUCINATION_KEYS


def test_load_model_passes_hallucination_silence_threshold_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """hallucination_silence_threshold > 0 のときだけ asr_options に入る。"""
    cfg = _mk_cfg(tmp_path, hallucination_silence_threshold=2.0)

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    asr = captured["kwargs"]["asr_options"]
    assert asr["hallucination_silence_threshold"] == 2.0


def test_load_model_respects_custom_temperatures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.env` で温度フォールバックを単一値に絞れば fallback 無効化できる。"""
    cfg = _mk_cfg(tmp_path, temperatures=(0.0,))

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    assert captured["kwargs"]["asr_options"]["temperatures"] == [0.0]


def test_load_model_passes_vad_method_silero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """vad_method=silero が load_model に渡されること(pyannote ハング回避)。"""
    cfg = _mk_cfg(tmp_path, vad_method="silero")

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    assert captured["kwargs"]["vad_method"] == "silero"


def test_load_model_passes_vad_method_pyannote_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """指定無しなら pyannote が渡される(WhisperX のデフォルト合わせ)。"""
    cfg = _mk_cfg(tmp_path, vad_method="pyannote")

    captured: dict = {}
    _install_whisperx_stub(monkeypatch, captured)

    import transcribe

    transcribe._model_cache.clear()
    transcribe._load_model(cfg)

    assert captured["kwargs"]["vad_method"] == "pyannote"


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
