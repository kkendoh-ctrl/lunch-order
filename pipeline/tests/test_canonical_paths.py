"""config.canonical_date_folder と path 解決の挙動テスト。

`inbox/録音 138.m4a` のような非 canonical な配置でも、
metadata / mtime / "_undated" にフォールバックして、
`vault/録音/inbox/...` のような変なフォルダを作らないことを確認。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from config import (
    Config,
    canonical_date_folder,
    canonical_time,
    note_path_for,
    skipped_marker_path_for,
    transcript_path_for,
)


def _mk_cfg(tmp_path: Path) -> Config:
    vault = tmp_path / "vault"
    return Config(
        jpr_inbox=tmp_path / "inbox",
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
        whisper_initial_prompt_path=None,
        whisper_align_enabled=False,
        whisper_vad_method="silero",
        file_stable_wait_s=5,
        file_stable_poll_s=2,
        anthropic_api_key="",
        anthropic_model="claude-opus-4-7",
        anthropic_max_tokens=8192,
        anthropic_effort="medium",
        structuring_prompt_path=None,
    )


def _touch(path: Path, mtime: datetime | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * 64)
    if mtime is not None:
        ts = mtime.timestamp()
        os.utime(path, (ts, ts))
    return path


# -------------------- canonical_date_folder --------------------


def test_canonical_passes_through_date_folder(tmp_path: Path) -> None:
    audio = _touch(tmp_path / "2026-05-23" / "13-39-19.m4a")
    assert canonical_date_folder(audio) == "2026-05-23"


def test_canonical_uses_mtime_for_non_date_parent(tmp_path: Path) -> None:
    mtime = datetime(2024, 11, 13, 15, 30, 0, tzinfo=timezone.utc)
    audio = _touch(tmp_path / "inbox" / "録音 138.m4a", mtime=mtime)
    assert canonical_date_folder(audio) == "2024-11-13"


def test_canonical_metadata_overrides_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mtime = datetime(2020, 1, 1, tzinfo=timezone.utc)
    audio = _touch(tmp_path / "inbox" / "voice.m4a", mtime=mtime)
    monkeypatch.setattr(
        config, "_try_audio_metadata_date", lambda p: "2024-11-13"
    )
    assert canonical_date_folder(audio) == "2024-11-13"


def test_canonical_falls_back_to_undated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = _touch(tmp_path / "weird" / "x.m4a")
    monkeypatch.setattr(config, "_try_audio_metadata_date", lambda p: None)
    monkeypatch.setattr(config, "_try_mtime_date", lambda p: None)
    assert canonical_date_folder(audio) == "_undated"


def test_canonical_rejects_partial_date_match(tmp_path: Path) -> None:
    # "2026-05-2" は YYYY-MM-DD でないので fallback されるべき
    mtime = datetime(2024, 11, 13, tzinfo=timezone.utc)
    audio = _touch(tmp_path / "2026-05-2" / "x.m4a", mtime=mtime)
    assert canonical_date_folder(audio) == "2024-11-13"


# -------------------- path resolution --------------------


def test_note_path_for_canonical_parent(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    audio = _touch(cfg.jpr_inbox / "2026-05-23" / "13-39-19.m4a")
    assert (
        note_path_for(cfg, audio)
        == cfg.notes_dir / "2026-05-23" / "13-39-19.md"
    )


def test_note_path_for_inbox_root_uses_mtime(tmp_path: Path) -> None:
    """これが今回の修正の本題: `inbox/録音 138.m4a` を直接 test/batch すると
    旧コードは `vault/録音/inbox/録音 138.md` を作っていたバグ。
    mtime から日付フォルダを決めるようにした。"""
    cfg = _mk_cfg(tmp_path)
    mtime = datetime(2024, 11, 13, tzinfo=timezone.utc)
    audio = _touch(cfg.jpr_inbox / "録音 138.m4a", mtime=mtime)

    out = note_path_for(cfg, audio)
    assert out == cfg.notes_dir / "2024-11-13" / "録音 138.md"
    # 念のため "inbox" が日付フォルダになっていない
    assert "inbox" not in out.parent.parts


def test_transcript_path_for_inbox_root_uses_mtime(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    mtime = datetime(2024, 11, 13, tzinfo=timezone.utc)
    audio = _touch(cfg.jpr_inbox / "test_30sec.m4a", mtime=mtime)
    assert (
        transcript_path_for(cfg, audio)
        == cfg.transcripts_dir / "2024-11-13" / "test_30sec.json"
    )


def test_skipped_marker_path_for_inbox_root_uses_mtime(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    mtime = datetime(2024, 11, 13, tzinfo=timezone.utc)
    audio = _touch(cfg.jpr_inbox / "noise.m4a", mtime=mtime)
    assert (
        skipped_marker_path_for(cfg, audio)
        == cfg.transcripts_dir / "2024-11-13" / "noise.skipped"
    )


# -------------------- canonical_time --------------------


def test_canonical_time_from_stem(tmp_path: Path) -> None:
    """stem が HH-MM-SS 形式なら時刻として展開。"""
    audio = _touch(tmp_path / "2026-05-23" / "13-39-19.m4a")
    assert canonical_time(audio) == "13:39:19"


def test_canonical_time_from_mtime(tmp_path: Path) -> None:
    """非 canonical stem なら mtime を見る。"""
    mtime = datetime(2024, 11, 13, 9, 30, 0, tzinfo=timezone.utc)
    audio = _touch(tmp_path / "inbox" / "test_5min.m4a", mtime=mtime)
    assert canonical_time(audio) == "09:30:00"


def test_canonical_time_metadata_overrides_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MP4 メタが取れれば mtime より優先。"""
    mtime = datetime(2020, 1, 1, tzinfo=timezone.utc)
    audio = _touch(tmp_path / "inbox" / "voice.m4a", mtime=mtime)
    monkeypatch.setattr(config, "_try_audio_metadata_time", lambda p: "15:30:45")
    assert canonical_time(audio) == "15:30:45"


def test_canonical_time_falls_back_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """全部失敗したら "00:00:00"(空文字や stem 残りは絶対返さない)。"""
    audio = _touch(tmp_path / "inbox" / "weird.m4a")
    monkeypatch.setattr(config, "_try_audio_metadata_time", lambda p: None)
    monkeypatch.setattr(config, "_try_mtime_time", lambda p: None)
    assert canonical_time(audio) == "00:00:00"


def test_canonical_time_always_hhmmss_format(tmp_path: Path) -> None:
    """戻り値は必ず HH:MM:SS パターンに合致。"""
    import re

    for name in ("13-39-19.m4a", "test_5min.m4a", "録音 138.m4a"):
        audio = _touch(
            tmp_path / "x" / name,
            mtime=datetime(2024, 11, 13, 1, 2, 3, tzinfo=timezone.utc),
        )
        out = canonical_time(audio)
        assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", out), f"{name} → {out}"
