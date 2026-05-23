"""importer.py のテスト。mutagen 無しでも純粋な path 生成 + mtime fallback
が動くことを確認。"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import importer
from config import Config


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


def _make_audio(tmp_path: Path, name: str, mtime: datetime | None = None) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\x00" * 100)  # 100 byte ダミー
    if mtime:
        ts = mtime.timestamp()
        os.utime(p, (ts, ts))
    return p


# -------------------- 純粋関数 --------------------


def test_format_target_path() -> None:
    inbox = Path("/inbox")
    dt = datetime(2024, 11, 13, 15, 30, 45, tzinfo=timezone.utc)
    assert importer._format_target_path(inbox, dt) == Path(
        "/inbox/2024-11-13/15-30-45.m4a"
    )


def test_ensure_unique_passthrough_when_free(tmp_path: Path) -> None:
    target = tmp_path / "13-39-19.m4a"
    assert importer._ensure_unique(target) == target


def test_ensure_unique_collision(tmp_path: Path) -> None:
    target = tmp_path / "13-39-19.m4a"
    target.write_bytes(b"x")
    out = importer._ensure_unique(target)
    assert out == tmp_path / "13-39-19-2.m4a"
    out.write_bytes(b"y")
    out2 = importer._ensure_unique(target)
    assert out2 == tmp_path / "13-39-19-3.m4a"


def test_mtime_date_roundtrip(tmp_path: Path) -> None:
    target = datetime(2024, 11, 13, 15, 30, 45, tzinfo=timezone.utc)
    p = _make_audio(tmp_path, "audio.m4a", mtime=target)
    out = importer._mtime_date(p)
    assert out is not None
    # ファイルシステムの解像度による誤差を許容(±2 秒)
    assert abs((out - target).total_seconds()) < 2


# -------------------- import_one --------------------


def test_import_one_uses_mtime_when_no_metadata(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    src = _make_audio(
        tmp_path / "src",
        "録音 142.m4a",
        mtime=datetime(2024, 11, 13, 15, 30, 45, tzinfo=timezone.utc),
    )
    result = importer.import_one(src, cfg)
    assert result.date_source == "mtime"
    assert result.dest is not None
    assert result.dest.parent == cfg.jpr_inbox / "2024-11-13"
    # 時刻はファイルシステム解像度の都合で 1-2 秒ずれ得るので名前は確認しない
    assert result.dest.suffix == ".m4a"
    assert result.dest.exists()
    # 元ファイルは残る
    assert src.exists()


def test_import_one_metadata_overrides_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _mk_cfg(tmp_path)
    src = _make_audio(
        tmp_path / "src",
        "audio.m4a",
        mtime=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    # メタが取れた体にする
    metadata_dt = datetime(2024, 11, 13, 15, 30, 45, tzinfo=timezone.utc)
    monkeypatch.setattr(
        importer, "_try_audio_metadata_date", lambda p: metadata_dt
    )
    result = importer.import_one(src, cfg)
    assert result.date_source == "metadata"
    assert result.dest is not None
    assert result.dest == cfg.jpr_inbox / "2024-11-13" / "15-30-45.m4a"


def test_import_one_undated_when_no_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _mk_cfg(tmp_path)
    src = _make_audio(tmp_path / "src", "weird.m4a")
    monkeypatch.setattr(importer, "_try_audio_metadata_date", lambda p: None)
    monkeypatch.setattr(importer, "_mtime_date", lambda p: None)
    result = importer.import_one(src, cfg)
    assert result.date_source == "undated"
    assert result.dest is not None
    assert result.dest.parent == cfg.jpr_inbox / "_undated"
    assert result.dest.name == "weird.m4a"


def test_import_one_collision_gets_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _mk_cfg(tmp_path)
    metadata_dt = datetime(2024, 11, 13, 15, 30, 45, tzinfo=timezone.utc)
    monkeypatch.setattr(importer, "_try_audio_metadata_date", lambda p: metadata_dt)

    src1 = _make_audio(tmp_path / "src1", "a.m4a")
    src2 = _make_audio(tmp_path / "src2", "b.m4a")
    r1 = importer.import_one(src1, cfg)
    r2 = importer.import_one(src2, cfg)
    assert r1.dest == cfg.jpr_inbox / "2024-11-13" / "15-30-45.m4a"
    assert r2.dest == cfg.jpr_inbox / "2024-11-13" / "15-30-45-2.m4a"


def test_import_one_missing_file(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    result = importer.import_one(tmp_path / "ghost.m4a", cfg)
    assert result.dest is None
    assert result.date_source == "error"


# -------------------- import_directory --------------------


def test_import_directory_scans_recursive(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    source = tmp_path / "src"
    _make_audio(source, "a.m4a", mtime=datetime(2024, 11, 1, tzinfo=timezone.utc))
    _make_audio(source / "sub", "b.m4a", mtime=datetime(2024, 11, 2, tzinfo=timezone.utc))
    _make_audio(source, "c.mp3", mtime=datetime(2024, 11, 3, tzinfo=timezone.utc))
    _make_audio(source, "ignore.txt")  # 拡張子マッチしないので飛ばす

    results = importer.import_directory(source, cfg)
    assert len(results) == 3
    assert all(r.dest is not None for r in results)
    # 全ファイルが日付フォルダに振り分けられる
    by_dir = {r.dest.parent.name for r in results}
    assert by_dir == {"2024-11-01", "2024-11-02", "2024-11-03"}


def test_import_directory_empty(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    source = tmp_path / "empty"
    source.mkdir()
    assert importer.import_directory(source, cfg) == []
