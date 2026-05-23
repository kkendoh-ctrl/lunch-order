"""note_writer.py の生成テスト(Claude / WhisperX なしで走る)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import note_writer
from config import Config


def _mk_cfg(tmp_path: Path) -> Config:
    return Config(
        jpr_inbox=tmp_path / "iCloud Drive" / "Just Press Record",
        vault=tmp_path / "iCloud Drive" / "音声記憶",
        transcripts_dir=tmp_path / "iCloud Drive" / "音声記憶" / "_transcripts",
        notes_dir=tmp_path / "iCloud Drive" / "音声記憶" / "録音",
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


def _transcript() -> dict:
    return {
        "audio_path": "/tmp/Just Press Record/2026-05-23/13-39-19.m4a",
        "duration_s": 323.0,
        "model": "large-v3",
        "language": "ja",
        "date": "2026-05-23",
        "time": "13:39:19",
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "こんにちは、田中です"},
            {"start": 2.5, "end": 5.1, "text": "モルック大会の件で連絡しました"},
        ],
        "text": "こんにちは、田中です モルック大会の件で連絡しました",
    }


def _structured_result() -> dict:
    return {
        "structured": {
            "date": "2026-05-23",
            "time": "13:39:19",
            "duration_s": 323,
            "contexts": [
                {
                    "start_time": "00:00:00",
                    "end_time": "00:05:23",
                    "title": "田中さんとの電話",
                    "counterpart": ["田中さん"],
                    "topics": ["モルック大会", "備品調達"],
                    "locations": ["総合体育館"],
                    "domains": ["業務"],
                    "importance": 4,
                    "sentiment": "ニュートラル",
                    "summary": "田中さんから来週のモルック大会の備品について連絡。見積もり確認が必要。",
                    "todos": [
                        {
                            "text": "来週までに見積もり確認",
                            "due": "2026-05-30",
                            "assignee": "self",
                        }
                    ],
                    "key_points": ["参加者は50名見込み", "備品は前年使い回し可"],
                    "open_questions": ["雨天時の代替会場(要確認)"],
                }
            ],
        },
        "model": "claude-opus-4-7",
        "structured_at": "2026-05-23T13:45:00Z",
        "usage": {
            "input_tokens": 1234,
            "output_tokens": 567,
            "cache_creation_input_tokens": 1000,
            "cache_read_input_tokens": 0,
        },
    }


def test_render_basic(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    audio = (
        tmp_path / "iCloud Drive" / "Just Press Record" / "2026-05-23" / "13-39-19.m4a"
    )
    body = note_writer.render_note(_transcript(), _structured_result(), audio, cfg)

    # フロントマター
    assert body.startswith("---\n")
    assert "date: '2026-05-23'" in body or "date: 2026-05-23" in body
    assert "duration: 5m23s" in body
    assert "importance: 4" in body
    # tags に 業務 と 重要 が入る
    assert "業務" in body
    assert "重要" in body
    # wikilink
    assert "[[田中さん]]" in body
    assert "[[モルック大会]]" in body
    assert "[[総合体育館]]" in body
    # 要約
    assert "見積もり確認が必要" in body
    # ToDo
    assert "- [ ] 来週までに見積もり確認 (期限: 2026-05-30) #todo" in body
    # キーポイント
    assert "参加者は50名見込み" in body
    # 全文(タイムスタンプ付き)
    assert "[00:00] こんにちは、田中です" in body
    assert "[00:02] モルック大会の件で連絡しました" in body
    # 日次ノートリンク
    assert "[[2026-05-23]]" in body
    # 原音への相対リンク
    assert "../../Just%20Press%20Record/2026-05-23/13-39-19.m4a" in body


def test_render_empty_contexts(tmp_path: Path) -> None:
    """contexts: [] (Claude が雑談と判断したケース)。"""
    cfg = _mk_cfg(tmp_path)
    audio = (
        tmp_path / "iCloud Drive" / "Just Press Record" / "2026-05-23" / "13-39-19.m4a"
    )
    result = {
        "structured": {"date": "2026-05-23", "time": "13:39:19", "contexts": []},
        "model": "claude-opus-4-7",
        "structured_at": "2026-05-23T13:45:00Z",
        "usage": {},
    }
    body = note_writer.render_note(_transcript(), result, audio, cfg)
    assert "Claude が「雑談・テスト録音」と判断" in body
    # 全文セクションは出る
    assert "[00:00] こんにちは、田中です" in body


def test_render_multiple_contexts(tmp_path: Path) -> None:
    """1録音に複数コンテキスト。"""
    cfg = _mk_cfg(tmp_path)
    audio = (
        tmp_path / "iCloud Drive" / "Just Press Record" / "2026-05-23" / "13-39-19.m4a"
    )
    result = {
        "structured": {
            "date": "2026-05-23",
            "time": "13:39:19",
            "contexts": [
                {
                    "title": "電話前半",
                    "domains": ["業務"],
                    "importance": 3,
                    "summary": "前半の要約",
                    "counterpart": ["田中さん"],
                    "topics": [],
                    "locations": [],
                    "todos": [],
                    "key_points": [],
                    "open_questions": [],
                    "sentiment": "ニュートラル",
                },
                {
                    "title": "話題転換: 家族の話",
                    "domains": ["私的", "家族"],
                    "importance": 2,
                    "summary": "後半の要約",
                    "counterpart": ["田中さん"],
                    "topics": [],
                    "locations": [],
                    "todos": [],
                    "key_points": [],
                    "open_questions": [],
                    "sentiment": "ポジティブ",
                },
            ],
        },
        "model": "claude-opus-4-7",
        "structured_at": "2026-05-23T13:45:00Z",
        "usage": {},
    }
    body = note_writer.render_note(_transcript(), result, audio, cfg)
    assert "## 電話前半" in body
    assert "## 話題転換: 家族の話" in body
    # 領域タグ統合
    assert "業務" in body
    assert "私的" in body
    assert "家族" in body
    # 最大重要度3(<4)なので「重要」タグは付かない
    assert "- 重要\n" not in body


def test_save_note_creates_dirs(tmp_path: Path) -> None:
    out = tmp_path / "vault" / "録音" / "2026-05-23" / "13-39-19.md"
    note_writer.save_note("# Hello\n", out)
    assert out.exists()
    assert out.read_text(encoding="utf-8") == "# Hello\n"
