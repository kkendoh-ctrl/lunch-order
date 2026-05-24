"""reminders.py のテスト。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import reminders
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


def test_escape_text_handles_special_chars() -> None:
    assert reminders._escape_text("foo;bar") == "foo\\;bar"
    assert reminders._escape_text("a,b") == "a\\,b"
    assert reminders._escape_text("line1\nline2") == "line1\\nline2"
    assert reminders._escape_text("back\\slash") == "back\\\\slash"
    assert reminders._escape_text("") == ""


def test_format_date_value() -> None:
    assert reminders._format_date_value("2026-05-30") == "20260530"
    assert reminders._format_date_value(None) is None
    assert reminders._format_date_value("") is None
    assert reminders._format_date_value("invalid") is None
    assert reminders._format_date_value("2026/05/30") is None


def test_todo_uid_deterministic() -> None:
    assert reminders.todo_uid("13-39-19", 0) == "13-39-19-0@voice-pipeline"
    assert reminders.todo_uid("13-39-19", 2) == "13-39-19-2@voice-pipeline"


def test_render_calendar_basic() -> None:
    todos = [
        {
            "uid": "13-39-19-0@voice-pipeline",
            "summary": "見積もり確認",
            "due": "2026-05-30",
            "description": "from 2026-05-23",
        }
    ]
    out = reminders.render_calendar(todos)
    # CRLF 改行
    assert "\r\n" in out
    assert out.endswith("\r\n")
    # 必須ヘッダ
    assert "BEGIN:VCALENDAR" in out
    assert "VERSION:2.0" in out
    assert "END:VCALENDAR" in out
    # VTODO
    assert "BEGIN:VTODO" in out
    assert "UID:13-39-19-0@voice-pipeline" in out
    assert "SUMMARY:見積もり確認" in out
    assert "DUE;VALUE=DATE:20260530" in out
    assert "DESCRIPTION:from 2026-05-23" in out
    assert "STATUS:NEEDS-ACTION" in out
    assert "END:VTODO" in out


def test_render_calendar_without_due() -> None:
    todos = [{"uid": "x-0", "summary": "期限なしタスク"}]
    out = reminders.render_calendar(todos)
    assert "SUMMARY:期限なしタスク" in out
    # DUE 行は無い
    assert "DUE:" not in out
    assert "DUE;" not in out


def test_render_calendar_multiple_todos() -> None:
    todos = [
        {"uid": "a-0", "summary": "task A", "due": "2026-06-01"},
        {"uid": "b-0", "summary": "task B"},
        {"uid": "c-0", "summary": "task C", "due": "2026-06-02"},
    ]
    out = reminders.render_calendar(todos)
    assert out.count("BEGIN:VTODO") == 3
    assert out.count("END:VTODO") == 3
    # 順序保持
    a_idx = out.find("UID:a-0")
    b_idx = out.find("UID:b-0")
    c_idx = out.find("UID:c-0")
    assert 0 < a_idx < b_idx < c_idx


def test_render_calendar_empty() -> None:
    out = reminders.render_calendar([])
    assert "BEGIN:VCALENDAR" in out
    assert "END:VCALENDAR" in out
    assert "BEGIN:VTODO" not in out


def test_escape_in_summary() -> None:
    todos = [
        {
            "uid": "x-0",
            "summary": "A, B; C\nD",
        }
    ]
    out = reminders.render_calendar(todos)
    assert "SUMMARY:A\\, B\\; C\\nD" in out


def test_write_calendar_creates_dir(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    out = reminders.write_calendar(
        [{"uid": "x-0", "summary": "テスト"}], cfg
    )
    assert out == cfg.vault / "_reminders" / "todos.ics"
    assert out.exists()
    assert "SUMMARY:テスト" in out.read_text(encoding="utf-8")


def test_write_calendar_empty_still_writes(tmp_path: Path) -> None:
    """ToDo が無くてもファイルは書く(以前あったものを消す効果)。"""
    cfg = _mk_cfg(tmp_path)
    out = reminders.write_calendar([], cfg)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "BEGIN:VCALENDAR" in text
    assert "BEGIN:VTODO" not in text
