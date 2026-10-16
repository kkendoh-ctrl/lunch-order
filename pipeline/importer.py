"""Phase 5+: 任意フォルダの音声を canonical inbox layout にコピー取込みする。

iOS 純正ボイスメモなど Just Press Record 以外のソースから過去録音をまとめて
パイプラインに流すための片道変換ツール。

設計:
- 元ファイルは絶対に触らない(コピー)。失敗時もロールバック不要
- 日時推定は (1) 音声メタの MP4 ©day → (2) ファイル mtime の順
- 両方ダメなら `<inbox>/_undated/<元のファイル名>` に隔離
- 同名衝突時は `-2`, `-3` を suffix
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import Config


_AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".mp4"}


@dataclass(frozen=True)
class ImportResult:
    src: Path
    dest: Path | None  # None なら失敗
    date_source: str  # "metadata" / "mtime" / "undated" / "error"
    error: str = ""


def _try_audio_metadata_date(path: Path) -> datetime | None:
    """mutagen で MP4 `©day` atom から日時を取り出す(オプション依存)。

    mutagen 未インストールならば None。Voice Memos は通常この atom に
    `2024-11-13T15:30:00Z` 形式で録音時刻を入れる。"""
    try:
        from mutagen.mp4 import MP4
    except ImportError:
        return None
    try:
        f = MP4(str(path))
        if not f.tags:
            return None
        raw = f.tags.get("\xa9day") or f.tags.get("\xa9DAY")
        if not raw:
            return None
        s = str(raw[0]).strip()
        # 末尾 Z は UTC、無しは naive 扱い
        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _mtime_date(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _format_target_path(inbox: Path, dt: datetime) -> Path:
    """YYYY-MM-DD/HH-MM-SS.m4a 形式の inbox 内 path。"""
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H-%M-%S")
    return inbox / date_str / f"{time_str}.m4a"


def _ensure_unique(target: Path) -> Path:
    """target が既存ならば `<stem>-2.m4a`, `-3` ... と suffix。"""
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    n = 2
    while True:
        candidate = target.parent / f"{stem}-{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def import_one(src: Path, cfg: Config) -> ImportResult:
    """1ファイルを canonical inbox にコピーする。"""
    if not src.exists() or not src.is_file():
        return ImportResult(
            src=src, dest=None, date_source="error", error="not a file"
        )

    dt = _try_audio_metadata_date(src)
    date_source = "metadata"
    if dt is None:
        dt = _mtime_date(src)
        date_source = "mtime" if dt is not None else "undated"

    if dt is None:
        undated_dir = cfg.jpr_inbox / "_undated"
        undated_dir.mkdir(parents=True, exist_ok=True)
        dest = _ensure_unique(undated_dir / src.name)
    else:
        target = _format_target_path(cfg.jpr_inbox, dt)
        target.parent.mkdir(parents=True, exist_ok=True)
        dest = _ensure_unique(target)

    try:
        shutil.copy2(src, dest)
    except OSError as e:
        return ImportResult(
            src=src, dest=None, date_source="error", error=str(e)
        )
    return ImportResult(src=src, dest=dest, date_source=date_source)


def import_directory(source: Path, cfg: Config) -> list[ImportResult]:
    """source 配下を再帰的に走査、`.m4a` 等を順次取込み。"""
    out: list[ImportResult] = []
    for p in sorted(source.rglob("*")):
        if p.suffix.lower() not in _AUDIO_EXTS:
            continue
        if not p.is_file():
            continue
        out.append(import_one(p, cfg))
    return out
