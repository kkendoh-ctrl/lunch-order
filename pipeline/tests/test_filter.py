"""filter.py の境界値テスト。WhisperX 無しで動かせる。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
from pydub import AudioSegment
from pydub.generators import Sine, WhiteNoise

# パッケージとしてではなく単独ファイル群として走らせる前提
sys.path.insert(0, str(Path(__file__).parent.parent))

import filter as audio_filter
from config import Config


def _mk_cfg(tmp_path: Path) -> Config:
    return Config(
        jpr_inbox=tmp_path / "jpr",
        vault=tmp_path / "vault",
        transcripts_dir=tmp_path / "vault" / "_transcripts",
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
    )


def _save(audio: AudioSegment, tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    audio.export(p, format="wav")
    return p


def test_too_short(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    # 5秒のサイン波
    audio = Sine(440).to_audio_segment(duration=5000)
    p = _save(audio, tmp_path, "short.wav")
    r = audio_filter.evaluate(p, cfg)
    assert r.skip is True
    assert r.reason == "too_short"


def test_long_enough_non_silent(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    # 15秒のホワイトノイズ(無音じゃない)
    audio = WhiteNoise().to_audio_segment(duration=15000).apply_gain(-10)
    p = _save(audio, tmp_path, "noise.wav")
    r = audio_filter.evaluate(p, cfg)
    assert r.skip is False
    assert r.reason == ""


def test_mostly_silent(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    # 15秒の無音(マイナス無限大に近い dBFS)
    audio = AudioSegment.silent(duration=15000)
    p = _save(audio, tmp_path, "silent.wav")
    r = audio_filter.evaluate(p, cfg)
    assert r.skip is True
    assert r.reason == "mostly_silent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
