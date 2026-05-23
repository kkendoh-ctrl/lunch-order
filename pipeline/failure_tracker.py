"""Phase 5a: 失敗ファイルの記録と再実行。

`_process_one` の各段階(filter/transcribe/structure/note_write/aggregate)で
例外が起きたら `_failed/YYYY-MM-DD/HH-MM-SS.json` に状況を残す。成功時は消す。

CLI:
- `python main.py failed` で一覧
- `python main.py retry` で全部 / `retry <audio>` で個別
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import Config


_ERROR_KEYWORDS = (
    "filter_error",
    "transcribe_error",
    "structure_error",
    "note_write_error",
    "aggregate_error",
    "transcript_read_error",
)


@dataclass(frozen=True)
class FailureRecord:
    audio_path: Path
    phase: str
    error: str
    first_attempted_at: str
    last_attempted_at: str
    attempt_count: int
    marker_path: Path


def failure_marker_path(cfg: Config, audio_path: Path) -> Path:
    """audio_path → _failed/YYYY-MM-DD/HH-MM-SS.json"""
    date_folder = audio_path.parent.name
    stem = audio_path.stem
    return cfg.failed_dir / date_folder / f"{stem}.json"


def classify_phase(status: str) -> str:
    """`transcribe_error: foo` のような status 文字列から phase を抜く。"""
    for kw in _ERROR_KEYWORDS:
        if kw in status:
            return kw.removesuffix("_error")
    return "unknown"


def status_indicates_failure(status: str) -> bool:
    return any(kw in status for kw in _ERROR_KEYWORDS)


def record_failure(
    cfg: Config, audio_path: Path, phase: str, error: str
) -> Path:
    """失敗マーカーを書く。既存ならば attempt_count++ / first_attempted_at 保持。"""
    marker = failure_marker_path(cfg, audio_path)
    marker.parent.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if marker.exists():
        try:
            existing = json.loads(marker.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # 1 行に詰めて読みやすく(traceback はやめる)
    short_error = " ".join(error.splitlines())[:500]
    data = {
        "audio_path": str(audio_path),
        "phase": phase,
        "error": short_error,
        "first_attempted_at": existing.get("first_attempted_at", now),
        "last_attempted_at": now,
        "attempt_count": int(existing.get("attempt_count", 0)) + 1,
    }
    marker.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return marker


def clear_failure(cfg: Config, audio_path: Path) -> bool:
    """成功した時に呼ぶ。マーカーがあれば消す。返り値: 消したか。"""
    marker = failure_marker_path(cfg, audio_path)
    if marker.exists():
        try:
            marker.unlink()
            return True
        except OSError:
            return False
    return False


def list_failures(cfg: Config) -> list[FailureRecord]:
    """全失敗マーカーを読み出す。古い順。"""
    if not cfg.failed_dir.exists():
        return []
    out: list[FailureRecord] = []
    for f in sorted(cfg.failed_dir.glob("*/*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        try:
            out.append(
                FailureRecord(
                    audio_path=Path(data["audio_path"]),
                    phase=str(data.get("phase", "unknown")),
                    error=str(data.get("error", "")),
                    first_attempted_at=str(data.get("first_attempted_at", "")),
                    last_attempted_at=str(data.get("last_attempted_at", "")),
                    attempt_count=int(data.get("attempt_count", 1)),
                    marker_path=f,
                )
            )
        except (KeyError, ValueError):
            continue
    return out
