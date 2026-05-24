"""軽フィルタ: 長さ・無音率で明らかなノイズを除外。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydub import AudioSegment

from config import Config


@dataclass(frozen=True)
class FilterResult:
    skip: bool
    reason: str  # "" / "too_short" / "mostly_silent"
    duration_s: float
    silent_ratio: float


def evaluate(audio_path: Path, cfg: Config) -> FilterResult:
    audio = AudioSegment.from_file(audio_path)
    duration_s = len(audio) / 1000.0

    if duration_s < cfg.skip_duration_s:
        return FilterResult(
            skip=True, reason="too_short", duration_s=duration_s, silent_ratio=0.0
        )

    # 500ms ごとに dBFS を見る
    chunks = list(audio[::500])
    if not chunks:
        return FilterResult(
            skip=True, reason="too_short", duration_s=duration_s, silent_ratio=0.0
        )
    silent = sum(1 for c in chunks if c.dBFS < cfg.skip_silence_db)
    ratio = silent / len(chunks)

    if ratio > cfg.skip_silence_ratio:
        return FilterResult(
            skip=True, reason="mostly_silent", duration_s=duration_s, silent_ratio=ratio
        )

    return FilterResult(
        skip=False, reason="", duration_s=duration_s, silent_ratio=ratio
    )
