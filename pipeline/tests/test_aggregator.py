"""aggregator.py のテスト(Claude/WhisperX なしで走る)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

import aggregator
import note_writer
from config import Config


def _mk_cfg(tmp_path: Path) -> Config:
    vault = tmp_path / "iCloud Drive" / "音声記憶"
    return Config(
        jpr_inbox=tmp_path / "iCloud Drive" / "Just Press Record",
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


_DEFAULT_TODOS = [
    {"text": "来週までに見積もり確認", "due": "2026-05-30", "assignee": "self"}
]


def _structured(
    *,
    date="2026-05-23",
    time="13:39:19",
    counterpart=("田中さん",),
    topics=("モルック大会", "備品調達"),
    locations=("総合体育館",),
    importance=4,
    title="田中さんとの電話",
    summary="田中さんから来週のモルック大会の備品について連絡。見積もり確認が必要。",
    todos=...,
    domains=("業務",),
) -> dict:
    # `...` (Ellipsis) を「未指定」のセンチネルに使う。空 list 明示は尊重したい
    effective_todos = list(_DEFAULT_TODOS) if todos is ... else list(todos)
    return {
        "date": date,
        "time": time,
        "duration_s": 323,
        "contexts": [
            {
                "start_time": "00:00:00",
                "end_time": "00:05:23",
                "title": title,
                "counterpart": list(counterpart),
                "topics": list(topics),
                "locations": list(locations),
                "domains": list(domains),
                "importance": importance,
                "sentiment": "ニュートラル",
                "summary": summary,
                "todos": effective_todos,
                "key_points": ["参加者は50名見込み"],
                "open_questions": [],
            }
        ],
    }


def _transcript(time="13:39:19") -> dict:
    return {
        "audio_path": f"/tmp/Just Press Record/2026-05-23/{time.replace(':', '-')}.m4a",
        "duration_s": 323.0,
        "model": "large-v3",
        "language": "ja",
        "date": "2026-05-23",
        "time": time,
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "こんにちは、田中です"},
            {"start": 2.5, "end": 5.1, "text": "モルック大会の件で連絡しました"},
        ],
        "text": "",
    }


def _write_note(
    cfg: Config,
    *,
    date: str,
    hhmmss: str,
    structured: dict,
) -> Path:
    """note_writer を使って実際にノートを書く(統合テスト的に)。
    structured の date/time をファイル名に合わせる。"""
    audio = (
        cfg.jpr_inbox / date / f"{hhmmss}.m4a"
    )
    time = hhmmss.replace("-", ":")
    structured.setdefault("date", date)
    structured["date"] = date
    structured["time"] = time
    transcript = _transcript(time=time)
    transcript["date"] = date
    result = {
        "structured": structured,
        "model": "claude-opus-4-7",
        "structured_at": "2026-05-23T13:45:00Z",
        "usage": {},
    }
    body = note_writer.render_note(transcript, result, audio, cfg)
    out = cfg.notes_dir / date / f"{hhmmss}.md"
    note_writer.save_note(body, out)
    return out


# -------------------- 純粋関数 --------------------


def test_strip_wikilink() -> None:
    assert aggregator._strip_wikilink("[[田中さん]]") == "田中さん"
    assert aggregator._strip_wikilink("田中さん") == "田中さん"
    assert aggregator._strip_wikilink("[[人物/田中さん]]") == "田中さん"
    assert aggregator._strip_wikilink("[[人物/田中さん|タナカ]]") == "田中さん"
    assert aggregator._strip_wikilink("") == ""


def test_sanitize_filename() -> None:
    assert aggregator._sanitize_filename("普通の名前") == "普通の名前"
    assert aggregator._sanitize_filename("/危険/な\\名前?") == "_危険_な_名前_"
    assert aggregator._sanitize_filename("  spaced  ") == "spaced"


def test_collect_entities_deduplicates_and_strips() -> None:
    structured = {
        "contexts": [
            {
                "counterpart": ["[[田中さん]]", "田中さん"],
                "topics": ["モルック大会"],
                "locations": ["[[総合体育館]]"],
            },
            {
                "counterpart": ["山田さん"],
                "topics": ["モルック大会", "備品調達"],
                "locations": [],
            },
        ]
    }
    out = aggregator._collect_entities(structured)
    assert out["人物"] == ["田中さん", "山田さん"]
    assert out["トピック"] == ["モルック大会", "備品調達"]
    assert out["場所"] == ["総合体育館"]


def test_normalize_time_value_handles_yaml_int() -> None:
    # YAML 1.1 は 13:39:19 を 49159 (sexagesimal int) にする
    assert aggregator._normalize_time_value(49159, "13-39-19") == "13:39:19"
    assert aggregator._normalize_time_value(0, "00-00-00") == "00:00:00"


def test_normalize_time_value_str_passthrough() -> None:
    assert aggregator._normalize_time_value("09:00:00", "anything") == "09:00:00"


def test_normalize_time_value_fallback_to_stem() -> None:
    assert aggregator._normalize_time_value(None, "13-39-19") == "13:39:19"
    assert aggregator._normalize_time_value("", "14-22-05") == "14:22:05"


def test_extract_todos_parses_due() -> None:
    body = "## ToDo\n- [ ] 見積もり確認 (期限: 2026-05-30) #todo\n- [ ] 資料送付 #todo\n- [x] 完了済み #todo\n"
    todos = aggregator._extract_todos(body)
    assert len(todos) == 2
    assert todos[0]["text"] == "見積もり確認"
    assert todos[0]["due"] == "2026-05-30"
    assert todos[1]["text"] == "資料送付"
    assert todos[1]["due"] is None


def test_parse_note_handles_missing_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "no_fm.md"
    p.write_text("# Hello\nbody\n", encoding="utf-8")
    fm, body = aggregator._parse_note(p)
    assert fm == {}
    assert "body" in body


def test_parse_note_reads_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "with_fm.md"
    p.write_text(
        "---\ndate: 2026-05-23\ntags: [a, b]\n---\n\n# Title\nbody\n", encoding="utf-8"
    )
    fm, body = aggregator._parse_note(p)
    # YAML は date を datetime.date にする。aggregator は str() で寄せる前提
    assert str(fm["date"]) == "2026-05-23"
    assert fm["tags"] == ["a", "b"]
    assert body.startswith("# Title")


# -------------------- skeleton 生成 --------------------


def test_ensure_entity_skeletons_creates_missing(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    cfg.vault.mkdir(parents=True)
    created = aggregator.ensure_entity_skeletons(_structured(), cfg)
    assert created["人物"] == ["田中さん"]
    assert created["トピック"] == ["モルック大会", "備品調達"]
    assert created["場所"] == ["総合体育館"]

    # 実ファイルが書かれている
    person = cfg.vault / "人物" / "田中さん.md"
    assert person.exists()
    body = person.read_text(encoding="utf-8")
    assert "auto-skeleton" in body
    assert "# 田中さん" in body
    fm, _ = aggregator._parse_note(person)
    assert fm["type"] == "人物"
    assert fm["name"] == "田中さん"


def test_ensure_entity_skeletons_does_not_overwrite(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    cfg.vault.mkdir(parents=True)
    target = cfg.vault / "人物" / "田中さん.md"
    target.parent.mkdir(parents=True)
    target.write_text("手動編集済み\n", encoding="utf-8")

    created = aggregator.ensure_entity_skeletons(_structured(), cfg)
    assert "田中さん" not in created["人物"]
    assert target.read_text(encoding="utf-8") == "手動編集済み\n"


def test_ensure_entity_skeletons_ignores_invalid_names(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    cfg.vault.mkdir(parents=True)
    structured = {
        "contexts": [
            {"counterpart": ["  ", ""], "topics": ["."], "locations": []}
        ]
    }
    created = aggregator.ensure_entity_skeletons(structured, cfg)
    assert created == {"人物": [], "トピック": [], "場所": []}


# -------------------- 日次ノート --------------------


def test_regenerate_daily_note_aggregates_recordings(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _write_note(cfg, date="2026-05-23", hhmmss="13-39-19", structured=_structured())
    _write_note(
        cfg,
        date="2026-05-23",
        hhmmss="14-22-05",
        structured=_structured(
            counterpart=("山田さん",),
            topics=("予算協議",),
            locations=("市役所",),
            importance=2,
            title="山田さんと予算",
            summary="来期予算の見通しを共有",
            todos=[],
            domains=("業務",),
        ),
    )

    out = aggregator.regenerate_daily_note("2026-05-23", cfg)
    assert out is not None
    assert out == cfg.vault / "日次" / "2026-05-23.md"
    text = out.read_text(encoding="utf-8")
    # フロントマター
    assert "type: 日次" in text
    assert "recordings: 2" in text
    assert "important: 1" in text
    assert "todos: 1" in text
    # 録音への wikilink (録音/2026-05-23/...)
    assert "[[録音/2026-05-23/13-39-19]]" in text
    assert "[[録音/2026-05-23/14-22-05]]" in text
    # 時刻 (短縮形)
    assert "13:39" in text
    assert "14:22" in text
    # ToDo セクション
    assert "## ToDo" in text
    assert "2026-05-30 来週までに見積もり確認" in text
    # 重要セクション
    assert "## 重要" in text
    assert "重要度4" in text
    # 各録音の要約スニペット
    assert "見積もり確認が必要" in text
    assert "来期予算の見通し" in text


def test_regenerate_daily_note_returns_none_for_empty_date(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    cfg.vault.mkdir(parents=True)
    out = aggregator.regenerate_daily_note("2099-01-01", cfg)
    assert out is None
    assert not (cfg.vault / "日次" / "2099-01-01.md").exists()


# -------------------- 一覧 --------------------


def test_regenerate_index_notes_todo_and_important(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _write_note(
        cfg,
        date="2026-05-23",
        hhmmss="13-39-19",
        structured=_structured(importance=4),
    )
    _write_note(
        cfg,
        date="2026-05-22",
        hhmmss="09-00-00",
        structured=_structured(
            counterpart=("佐藤さん",),
            topics=("契約更新",),
            locations=(),
            importance=5,
            title="佐藤さん契約",
            summary="契約更新の合意",
            todos=[
                {"text": "契約書ドラフト送付", "due": None, "assignee": "self"}
            ],
            domains=("業務",),
        ),
    )

    out = aggregator.regenerate_index_notes(cfg)
    assert out["todo"].exists()
    assert out["important"].exists()

    todo_text = out["todo"].read_text(encoding="utf-8")
    # 期限ありが先頭
    assert "## 期限あり(1)" in todo_text
    assert "2026-05-30 来週までに見積もり確認" in todo_text
    # 期限なし
    assert "## 期限なし(1)" in todo_text
    assert "契約書ドラフト送付" in todo_text
    # 録音への link
    assert "[[録音/2026-05-23/13-39-19]]" in todo_text
    assert "[[録音/2026-05-22/09-00-00]]" in todo_text

    imp_text = out["important"].read_text(encoding="utf-8")
    assert "重要度 4-5 の録音 全 2 件" in imp_text
    assert "## 重要度 5(1)" in imp_text
    assert "## 重要度 4(1)" in imp_text
    # 新しい順
    p5_idx = imp_text.find("[[録音/2026-05-22/09-00-00]]")
    p4_idx = imp_text.find("[[録音/2026-05-23/13-39-19]]")
    assert p5_idx > 0 and p4_idx > 0
    # 5 のセクションに 09:00:00 が、4 のセクションに 13:39:19 が来る


def test_regenerate_index_notes_empty_vault(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    cfg.vault.mkdir(parents=True)
    out = aggregator.regenerate_index_notes(cfg)
    todo_text = out["todo"].read_text(encoding="utf-8")
    imp_text = out["important"].read_text(encoding="utf-8")
    assert "全 0 件" in todo_text
    assert "全 0 件" in imp_text
    # reminders_enabled=True がデフォルト → .ics も書かれる(空でも)
    assert "ics" in out
    ics_text = out["ics"].read_text(encoding="utf-8")
    assert "BEGIN:VCALENDAR" in ics_text
    assert "BEGIN:VTODO" not in ics_text


def test_regenerate_index_notes_writes_ics_with_todos(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _write_note(
        cfg,
        date="2026-05-23",
        hhmmss="13-39-19",
        structured=_structured(),  # 期限ありの 1 件
    )
    out = aggregator.regenerate_index_notes(cfg)
    ics = out["ics"].read_text(encoding="utf-8")
    assert "BEGIN:VTODO" in ics
    assert "SUMMARY:来週までに見積もり確認" in ics
    assert "DUE;VALUE=DATE:20260530" in ics
    assert "UID:13-39-19-0@voice-pipeline" in ics


def test_regenerate_index_notes_skips_ics_when_disabled(tmp_path: Path) -> None:
    from dataclasses import replace

    cfg = replace(_mk_cfg(tmp_path), reminders_enabled=False)
    _write_note(
        cfg, date="2026-05-23", hhmmss="13-39-19", structured=_structured()
    )
    out = aggregator.regenerate_index_notes(cfg)
    assert "ics" not in out
    assert not (cfg.vault / "_reminders" / "todos.ics").exists()


# -------------------- 統合 --------------------


def test_aggregate_after_note_full_flow(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    structured = _structured()
    note = _write_note(
        cfg, date="2026-05-23", hhmmss="13-39-19", structured=structured
    )
    audio = (
        cfg.jpr_inbox / "2026-05-23" / "13-39-19.m4a"
    )
    summary = aggregator.aggregate_after_note(structured, audio, cfg)

    # skeleton 作成
    assert "田中さん" in summary["skeletons"]["人物"]
    assert (cfg.vault / "人物" / "田中さん.md").exists()
    assert (cfg.vault / "トピック" / "モルック大会.md").exists()
    assert (cfg.vault / "場所" / "総合体育館.md").exists()
    # 日次
    assert summary["daily"] == cfg.vault / "日次" / "2026-05-23.md"
    assert summary["daily"].exists()
    # 一覧
    assert summary["indexes"]["todo"].exists()
    assert summary["indexes"]["important"].exists()


def test_aggregate_full_rebuilds_everything(tmp_path: Path) -> None:
    """既存ノートから全部再生成できる。"""
    cfg = _mk_cfg(tmp_path)
    _write_note(cfg, date="2026-05-23", hhmmss="13-39-19", structured=_structured())
    _write_note(
        cfg,
        date="2026-05-24",
        hhmmss="10-00-00",
        structured=_structured(
            counterpart=("山田さん",),
            topics=("予算",),
            locations=(),
            importance=3,
            title="山田さん",
            summary="予算の話",
            todos=[],
            domains=("業務",),
        ),
    )

    out = aggregator.aggregate_full(cfg)
    assert out["scanned"] == 2
    # skeleton: 田中さん, モルック大会, 備品調達, 総合体育館, 山田さん, 予算
    assert (cfg.vault / "人物" / "田中さん.md").exists()
    assert (cfg.vault / "人物" / "山田さん.md").exists()
    assert (cfg.vault / "トピック" / "予算.md").exists()
    # 日次 2 本
    assert {p.name for p in out["dailies"]} == {"2026-05-23.md", "2026-05-24.md"}
    # 一覧
    assert out["indexes"]["todo"].exists()


def test_summarize_note_picks_summary_section(tmp_path: Path) -> None:
    body = """## 田中さんとの電話

重要度: 4

### 要約
田中さんから連絡。来週の打ち合わせの件。
複数行になっても拾える。

### ToDo
- [ ] foo
"""
    fm = {}
    s = aggregator._summarize_note(fm, body)
    assert "田中さんから連絡" in s
    assert "複数行になっても拾える" in s
    # 見出しは含めない
    assert "###" not in s
