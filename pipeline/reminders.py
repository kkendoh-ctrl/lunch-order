"""Phase 5b: Apple Reminders 取込み用の VTODO 形式 (.ics) を Vault に書く。

iCloud Drive 経由で iPhone まで自動で届くので、iOS 側で以下のどちらかの
運用を想定:

1. Files アプリで `_reminders/todos.ics` を開き「リマインダーに追加」
2. ショートカット (Shortcuts) で `iCloud Drive/音声記憶/_reminders/todos.ics`
   を読んで Reminders.app に登録する自動化を組む

RFC 5545 VTODO を使う(VEVENT ではない)。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from config import Config


_REMINDERS_DIR = "_reminders"
_PRODID = "-//voice-pipeline//ja"


def _escape_text(text: str) -> str:
    """iCalendar TEXT 型のエスケープ(\\, ;, , 改行)。"""
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _format_date_value(due: str | None) -> str | None:
    """`YYYY-MM-DD` → `YYYYMMDD`。不正/欠落なら None。"""
    if not due:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", due.strip())
    if not m:
        return None
    return f"{m.group(1)}{m.group(2)}{m.group(3)}"


def _now_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def todo_uid(audio_stem: str, index: int) -> str:
    """UID は決定論的に。同じ録音から同じ ToDo が再生成された時に重複登録を
    避ける(Reminders.app は UID で identify する)。"""
    return f"{audio_stem}-{index}@voice-pipeline"


def _vtodo_lines(
    *,
    uid: str,
    summary: str,
    due: str | None,
    description: str,
    dtstamp: str,
) -> list[str]:
    lines = [
        "BEGIN:VTODO",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"SUMMARY:{_escape_text(summary)}",
        "STATUS:NEEDS-ACTION",
    ]
    due_val = _format_date_value(due)
    if due_val:
        lines.append(f"DUE;VALUE=DATE:{due_val}")
    if description:
        lines.append(f"DESCRIPTION:{_escape_text(description)}")
    lines.append("END:VTODO")
    return lines


def render_calendar(todos: list[dict]) -> str:
    """todos: [{uid, summary, due?, description?}, ...] → iCalendar 文字列。

    RFC 5545 は CRLF が必須なので "\\r\\n" で連結する。"""
    dtstamp = _now_utc_stamp()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_PRODID}",
        "METHOD:PUBLISH",
        "CALSCALE:GREGORIAN",
    ]
    for t in todos:
        lines.extend(
            _vtodo_lines(
                uid=str(t.get("uid", "")),
                summary=str(t.get("summary", "")),
                due=t.get("due"),
                description=str(t.get("description", "")),
                dtstamp=dtstamp,
            )
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def write_calendar(todos: list[dict], cfg: Config) -> Path:
    """`<vault>/_reminders/todos.ics` を書く。"""
    out_dir = cfg.vault / _REMINDERS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "todos.ics"
    out.write_text(render_calendar(todos), encoding="utf-8")
    return out
