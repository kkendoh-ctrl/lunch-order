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

from config import Config, canonical_date_folder


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
    date_folder = canonical_date_folder(audio_path)
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


# よく出るエラーパターン → 対処ヒント。再帰やキャプチャは不要なので普通の
# string search ベース(re.search で大文字小文字無視)。
_ERROR_HINTS: list[tuple[str, str]] = [
    (
        r"WinError 2|ffmpeg.*not found|No such file or directory.*ffmpeg",
        "ffmpeg が PATH に無い。`winget install Gyan.FFmpeg` 後に PowerShell 再起動",
    ),
    (
        r"OutOfMemoryError|out of memory|CUDA out of memory",
        ".env で WHISPER_MODEL を medium か small に落とすか、他のアプリ閉じる",
    ),
    (
        r"libcudart\.so|CUDA|cuDNN",
        ".env で WHISPER_DEVICE=cpu になっているか確認",
    ),
    (
        r"401|authentication_error|invalid_api_key|x-api-key",
        "ANTHROPIC_API_KEY が無効。https://console.anthropic.com で再発行 → .env 更新",
    ),
    (
        r"429|rate_limit",
        "Claude API のレート制限。数分待ってから python main.py retry",
    ),
    (
        r"unexpected keyword argument 'initial_prompt'",
        "WhisperX が古い。`pip install -U 'whisperx>=3.3.0'` で更新",
    ),
    (
        r"JSONDecodeError|応答から JSON を抽出できません",
        "Claude が JSON 以外を返した。_プロンプト/claude-structuring.md を見直す",
    ),
    (
        r"FileNotFoundError|指定されたファイルが見つかりません",
        "音声ファイルが消えた / Google Drive オフライン未設定。"
        "`failed --clean-stale` で消失マーカー削除可",
    ),
    (
        r"ANTHROPIC_API_KEY が未設定",
        ".env で ANTHROPIC_API_KEY=sk-ant-... を設定して再実行",
    ),
    (
        r"connection.*refused|timed out|timeout",
        "ネットワーク不安定。Claude API/HF へ到達できるか確認、しばらく後に retry",
    ),
]


def suggest_hint(error: str) -> str | None:
    """エラーメッセージから既知パターンを引いてヒント文字列を返す。
    マッチしなければ None。"""
    if not error:
        return None
    for pattern, hint in _ERROR_HINTS:
        if re.search(pattern, error, re.IGNORECASE):
            return hint
    return None


def cleanup_stale(cfg: Config) -> list[Path]:
    """失敗マーカーのうち、参照先の audio が見つからないものを削除する。

    Google Drive オフライン解除や手動削除などで元ファイルが消えた場合、
    retry しても無意味なので片付ける。返り値: 消したマーカーが指していた audio_path のリスト。"""
    removed: list[Path] = []
    for record in list_failures(cfg):
        if record.audio_path.exists():
            continue
        try:
            record.marker_path.unlink()
            removed.append(record.audio_path)
        except OSError:
            continue
    return removed
