"""failure_tracker.py のテスト。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import failure_tracker as ft
from config import Config


def _mk_cfg(tmp_path: Path) -> Config:
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
        anthropic_api_key="",
        anthropic_model="claude-opus-4-7",
        anthropic_max_tokens=8192,
        anthropic_effort="medium",
        structuring_prompt_path=None,
    )


def _audio(tmp_path: Path, date: str = "2026-05-23", stem: str = "13-39-19") -> Path:
    return tmp_path / "jpr" / date / f"{stem}.m4a"


def test_marker_path_layout(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    audio = _audio(tmp_path)
    p = ft.failure_marker_path(cfg, audio)
    assert p == cfg.vault / "_failed" / "2026-05-23" / "13-39-19.json"


def test_classify_phase() -> None:
    assert ft.classify_phase("transcribe_error: foo") == "transcribe"
    assert ft.classify_phase("structured(...) / aggregate_error: bar") == "aggregate"
    assert ft.classify_phase("structured(ctx=1) / aggregated(...)") == "unknown"


def test_status_indicates_failure() -> None:
    assert ft.status_indicates_failure("transcribe_error: foo")
    assert ft.status_indicates_failure("note_write_error: x")
    assert not ft.status_indicates_failure("structured(ctx=1) / aggregated(skeleton=0)")
    assert not ft.status_indicates_failure("skipped(too_short, 5.0s)")
    assert not ft.status_indicates_failure("already_processed")


def test_record_failure_creates_marker(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    audio = _audio(tmp_path)
    marker = ft.record_failure(cfg, audio, "transcribe", "boom\nstacktrace lines")
    assert marker.exists()
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["phase"] == "transcribe"
    assert data["audio_path"] == str(audio)
    assert data["attempt_count"] == 1
    # 改行が潰されている
    assert "\n" not in data["error"]


def test_record_failure_increments_count(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    audio = _audio(tmp_path)
    ft.record_failure(cfg, audio, "transcribe", "err1")
    ft.record_failure(cfg, audio, "transcribe", "err2")
    marker = ft.failure_marker_path(cfg, audio)
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["attempt_count"] == 2
    assert data["error"] == "err2"
    # first_attempted_at は初回のまま
    assert data["first_attempted_at"] != ""
    assert data["last_attempted_at"] >= data["first_attempted_at"]


def test_clear_failure(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    audio = _audio(tmp_path)
    ft.record_failure(cfg, audio, "transcribe", "err")
    assert ft.clear_failure(cfg, audio)
    assert not ft.failure_marker_path(cfg, audio).exists()
    # 二度目は False
    assert not ft.clear_failure(cfg, audio)


def test_list_failures_empty(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    assert ft.list_failures(cfg) == []


def test_list_failures_sorted(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    a1 = _audio(tmp_path, date="2026-05-22", stem="10-00-00")
    a2 = _audio(tmp_path, date="2026-05-23", stem="13-39-19")
    a3 = _audio(tmp_path, date="2026-05-22", stem="11-00-00")
    ft.record_failure(cfg, a1, "transcribe", "e1")
    ft.record_failure(cfg, a2, "structure", "e2")
    ft.record_failure(cfg, a3, "filter", "e3")
    fails = ft.list_failures(cfg)
    assert len(fails) == 3
    # 日付フォルダ + ファイル名 のソート: 2026-05-22/10-00-00, 22/11-00-00, 23/13-39-19
    assert fails[0].audio_path.name == "10-00-00.m4a"
    assert fails[1].audio_path.name == "11-00-00.m4a"
    assert fails[2].audio_path.name == "13-39-19.m4a"


def test_list_failures_skips_unparseable(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    audio = _audio(tmp_path)
    ft.record_failure(cfg, audio, "transcribe", "err")
    # 壊れた JSON を別途追加
    bad = cfg.failed_dir / "2026-05-23" / "11-00-00.json"
    bad.write_text("{not json", encoding="utf-8")
    fails = ft.list_failures(cfg)
    assert len(fails) == 1
    assert fails[0].audio_path.name == "13-39-19.m4a"
