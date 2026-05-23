"""structure.py の純粋関数テスト(Claude API 呼び出しなし)。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import structure


def test_extract_json_plain() -> None:
    raw = '{"date": "2026-05-23", "contexts": []}'
    assert structure._extract_json(raw) == {
        "date": "2026-05-23",
        "contexts": [],
    }


def test_extract_json_with_fence() -> None:
    raw = "```json\n" + '{"a": 1}' + "\n```"
    assert structure._extract_json(raw) == {"a": 1}


def test_extract_json_with_preamble() -> None:
    raw = "こちらが結果です:\n```json\n" + '{"a": 1, "b": [2, 3]}' + "\n```\n以上。"
    assert structure._extract_json(raw) == {"a": 1, "b": [2, 3]}


def test_extract_json_braces_only() -> None:
    raw = 'noise {"x": "y"} more noise'
    assert structure._extract_json(raw) == {"x": "y"}


def test_extract_json_raises_on_garbage() -> None:
    with pytest.raises(ValueError):
        structure._extract_json("これは JSON ではない普通の文章です")


def test_split_prompt_extracts_fence_content() -> None:
    template = """# Header

説明文。

```
あなたは音声記憶アシスタントです。

## 入力
{{TRANSCRIPT}}
```

補足
"""
    system = structure._split_prompt(template)
    assert "あなたは音声記憶アシスタント" in system
    assert "{{TRANSCRIPT}}" not in system


def test_split_prompt_no_fence() -> None:
    template = "プレーンなプロンプト本文。 {{TRANSCRIPT}} 末尾。"
    system = structure._split_prompt(template)
    assert system == "プレーンなプロンプト本文。"
    assert "TRANSCRIPT" not in system


def test_format_transcript_for_user() -> None:
    transcript = {
        "date": "2026-05-23",
        "time": "13:39:19",
        "duration_s": 12.5,
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "こんにちは"},
            {"start": 65.0, "end": 70.0, "text": "1分過ぎ"},
        ],
    }
    text = structure._format_transcript_for_user(transcript)
    assert "録音日時: 2026-05-23 13:39:19" in text
    assert "長さ: 12.5 秒" in text
    assert "[00:00] こんにちは" in text
    assert "[01:05] 1分過ぎ" in text


def test_enrich_transcript_meta_from_audio_path() -> None:
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    enriched = structure._enrich_transcript_meta({}, audio)
    assert enriched["date"] == "2026-05-23"
    assert enriched["time"] == "13:39:19"


def test_enrich_transcript_meta_preserves_existing() -> None:
    audio = Path("/x/Just Press Record/2026-05-23/13-39-19.m4a")
    enriched = structure._enrich_transcript_meta(
        {"date": "override", "time": "11:11:11"}, audio
    )
    assert enriched["date"] == "override"
    assert enriched["time"] == "11:11:11"
