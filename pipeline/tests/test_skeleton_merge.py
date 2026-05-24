"""skeleton_merge の単体テスト。

カバー:
- alias YAML 読み込み (正常 / バリデーションエラー)
- wikilink 書き換え (生 / |label / category/path / 部分一致しない別物)
- plan_merges (統合元あり/無し、skeleton マーカー有/無)
- apply_merges (dry-run / 本適用 / メモ転記 / 削除 / リネーム)
- format_*_report (例外なく文字列が出るかだけ)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import skeleton_merge
from config import Config


def _mk_cfg(tmp_path: Path) -> Config:
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    return Config(
        jpr_inbox=tmp_path / "inbox",
        vault=vault,
        transcripts_dir=vault / "_transcripts",
        notes_dir=vault / "録音",
        skip_duration_s=10,
        skip_silence_ratio=0.95,
        skip_silence_db=-40,
        whisper_model="large-v3-turbo",
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


def _mk_skeleton(vault: Path, category: str, name: str, memo: str = "") -> Path:
    """auto-skeleton マーカー付きの skeleton ファイルを作る。"""
    d = vault / category
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.md"
    body = (
        "---\n"
        f"type: {category}\n"
        f"name: {name}\n"
        "---\n\n"
        f"{skeleton_merge._SKELETON_MARKER}\n\n"
        f"# {name}\n\n"
        "## メモ\n\n"
        f"{memo if memo else '(関係性などを追記)'}\n\n"
        "## 関連録音\n\n"
        "(Obsidian のバックリンクに表示されます)\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def _mk_recording_note(vault: Path, date: str, time: str, links: list[str]) -> Path:
    d = vault / "録音" / date
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{time}.md"
    body = "---\ndate: " + date + "\n---\n\n"
    body += "# 録音\n\n"
    for link in links:
        body += f"- [[{link}]]\n"
    path.write_text(body, encoding="utf-8")
    return path


# -------------------- load_alias_table --------------------


def test_load_alias_table_basic(tmp_path: Path) -> None:
    alias = tmp_path / "alias.yaml"
    alias.write_text(
        "人物:\n"
        "  アイテックス: アイタックス\n"
        "  リアックスさん: リアックス\n"
        "トピック:\n"
        "  Aシステム: A\n"
        "場所: {}\n",
        encoding="utf-8",
    )
    entries = skeleton_merge.load_alias_table(alias)
    assert len(entries) == 3
    persons = [e for e in entries if e.category == "人物"]
    assert {(e.source, e.target) for e in persons} == {
        ("アイテックス", "アイタックス"),
        ("リアックスさん", "リアックス"),
    }


def test_load_alias_table_unknown_category(tmp_path: Path) -> None:
    alias = tmp_path / "alias.yaml"
    alias.write_text("会社:\n  A: B\n", encoding="utf-8")
    with pytest.raises(ValueError, match="未知カテゴリ"):
        skeleton_merge.load_alias_table(alias)


def test_load_alias_table_duplicate_source(tmp_path: Path) -> None:
    alias = tmp_path / "alias.yaml"
    alias.write_text(
        "人物:\n  A: B\n  A: C\n", encoding="utf-8"
    )
    # YAML パース時点で後勝ちで 1 件になるが、それ自体は load_alias_table 通過。
    entries = skeleton_merge.load_alias_table(alias)
    assert len(entries) == 1
    assert entries[0].target == "C"


def test_load_alias_table_self_alias(tmp_path: Path) -> None:
    alias = tmp_path / "alias.yaml"
    alias.write_text("人物:\n  A: A\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source と target が同じ"):
        skeleton_merge.load_alias_table(alias)


def test_load_alias_table_empty_value(tmp_path: Path) -> None:
    alias = tmp_path / "alias.yaml"
    alias.write_text("人物:\n  A: ''\n", encoding="utf-8")
    with pytest.raises(ValueError, match="空文字"):
        skeleton_merge.load_alias_table(alias)


# -------------------- rewrite_file_text --------------------


def test_rewrite_simple_wikilink() -> None:
    text = "see [[アイテックス]] and [[他]]"
    new, count = skeleton_merge.rewrite_file_text(text, "アイテックス", "アイタックス")
    assert count == 1
    assert "[[アイタックス]]" in new
    assert "[[他]]" in new


def test_rewrite_with_label() -> None:
    text = "[[アイテックス|アイテックス様]] meeting"
    new, count = skeleton_merge.rewrite_file_text(text, "アイテックス", "アイタックス")
    assert count == 1
    assert "[[アイタックス|アイテックス様]]" in new


def test_rewrite_with_category_path() -> None:
    text = "see [[人物/アイテックス]] today"
    new, count = skeleton_merge.rewrite_file_text(text, "アイテックス", "アイタックス")
    assert count == 1
    assert "[[人物/アイタックス]]" in new


def test_rewrite_no_match() -> None:
    text = "[[アイテックス商事]] is different"
    new, count = skeleton_merge.rewrite_file_text(text, "アイテックス", "アイタックス")
    assert count == 0
    assert new == text


def test_rewrite_multiple_occurrences() -> None:
    text = "[[X]] then [[X]] then [[人物/X|表示]]"
    new, count = skeleton_merge.rewrite_file_text(text, "X", "Y")
    assert count == 3
    assert "[[Y]]" in new
    assert "[[人物/Y|表示]]" in new


# -------------------- plan_merges --------------------


def test_plan_merges_basic(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _mk_skeleton(cfg.vault, "人物", "アイテックス")
    _mk_skeleton(cfg.vault, "人物", "アイタックス")
    _mk_recording_note(cfg.vault, "2026-05-23", "10-00-00", ["アイテックス", "他"])

    entries = [
        skeleton_merge.AliasEntry(
            category="人物", source="アイテックス", target="アイタックス"
        )
    ]
    plans = skeleton_merge.plan_merges(entries, cfg)
    assert len(plans) == 1
    p = plans[0]
    assert p.source_exists and p.target_exists
    assert p.source_is_skeleton and p.target_is_skeleton
    assert len(p.rewrites) == 1
    assert p.rewrites[0].occurrences == 1


def test_plan_merges_source_missing(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _mk_skeleton(cfg.vault, "人物", "アイタックス")

    entries = [
        skeleton_merge.AliasEntry(
            category="人物", source="アイテックス", target="アイタックス"
        )
    ]
    plans = skeleton_merge.plan_merges(entries, cfg)
    assert not plans[0].source_exists
    assert plans[0].notes  # skip 理由が記録される


def test_plan_merges_warn_handwritten(tmp_path: Path) -> None:
    """skeleton マーカーが消えてる(=手書きで埋まった)ケースは warning"""
    cfg = _mk_cfg(tmp_path)
    p = cfg.vault / "人物" / "瑞穂さん.md"
    p.parent.mkdir(parents=True)
    p.write_text(
        "---\ntype: 人物\nname: 瑞穂さん\n---\n\n"
        "# 瑞穂さん\n\n"
        "## メモ\n手書きの本格的なメモ。\n",
        encoding="utf-8",
    )
    _mk_skeleton(cfg.vault, "人物", "瑞穂")

    entries = [
        skeleton_merge.AliasEntry(
            category="人物", source="瑞穂さん", target="瑞穂"
        )
    ]
    plans = skeleton_merge.plan_merges(entries, cfg)
    assert plans[0].source_exists
    assert not plans[0].source_is_skeleton
    assert any("auto-skeleton マーカーを持たない" in n for n in plans[0].notes)


# -------------------- apply_merges --------------------


def test_apply_merges_dry_run_changes_nothing(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    src = _mk_skeleton(cfg.vault, "人物", "アイテックス")
    _mk_skeleton(cfg.vault, "人物", "アイタックス")
    note = _mk_recording_note(
        cfg.vault, "2026-05-23", "10-00-00", ["アイテックス"]
    )
    orig_note = note.read_text(encoding="utf-8")

    entries = [
        skeleton_merge.AliasEntry(
            category="人物", source="アイテックス", target="アイタックス"
        )
    ]
    plans = skeleton_merge.plan_merges(entries, cfg)
    report = skeleton_merge.apply_merges(plans, cfg, dry_run=True)

    assert src.exists()  # 削除されてない
    assert note.read_text(encoding="utf-8") == orig_note  # 書き換えられてない
    assert report.plans_applied == 1
    assert report.wikilinks_rewritten == 1


def test_apply_merges_actually_applies(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    src = _mk_skeleton(cfg.vault, "人物", "アイテックス")
    tgt = _mk_skeleton(cfg.vault, "人物", "アイタックス")
    note = _mk_recording_note(
        cfg.vault, "2026-05-23", "10-00-00", ["アイテックス", "他人"]
    )
    daily = cfg.vault / "日次" / "2026-05-23.md"
    daily.parent.mkdir(parents=True)
    daily.write_text(
        "# 2026-05-23\n\n- [[人物/アイテックス|アイテックス様]] 来訪\n",
        encoding="utf-8",
    )

    entries = [
        skeleton_merge.AliasEntry(
            category="人物", source="アイテックス", target="アイタックス"
        )
    ]
    plans = skeleton_merge.plan_merges(entries, cfg)
    report = skeleton_merge.apply_merges(plans, cfg, dry_run=False)

    assert not src.exists()
    assert tgt.exists()
    note_text = note.read_text(encoding="utf-8")
    assert "[[アイタックス]]" in note_text
    assert "[[アイテックス]]" not in note_text
    daily_text = daily.read_text(encoding="utf-8")
    assert "[[人物/アイタックス|アイテックス様]]" in daily_text
    assert report.plans_applied == 1
    assert report.sources_deleted == 1
    assert report.wikilinks_rewritten == 2  # 録音 1 + 日次 1


def test_apply_merges_rename_when_target_missing(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    src = _mk_skeleton(cfg.vault, "人物", "リアックスさん")
    tgt = cfg.vault / "人物" / "リアックス.md"

    entries = [
        skeleton_merge.AliasEntry(
            category="人物", source="リアックスさん", target="リアックス"
        )
    ]
    plans = skeleton_merge.plan_merges(entries, cfg)
    report = skeleton_merge.apply_merges(plans, cfg, dry_run=False)

    assert not src.exists()
    assert tgt.exists()
    text = tgt.read_text(encoding="utf-8")
    assert "name: リアックス" in text
    assert "# リアックス" in text
    assert report.sources_renamed == 1
    assert report.sources_deleted == 1


def test_apply_merges_transfers_handwritten_memo(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    src = _mk_skeleton(
        cfg.vault, "人物", "高瀬さん", memo="データゲン所属、係長。"
    )
    tgt = _mk_skeleton(cfg.vault, "人物", "データゲン高瀬")

    entries = [
        skeleton_merge.AliasEntry(
            category="人物", source="高瀬さん", target="データゲン高瀬"
        )
    ]
    plans = skeleton_merge.plan_merges(entries, cfg)
    report = skeleton_merge.apply_merges(plans, cfg, dry_run=False)

    assert not src.exists()
    tgt_text = tgt.read_text(encoding="utf-8")
    assert "## 統合元: 高瀬さん のメモ" in tgt_text
    assert "データゲン所属、係長。" in tgt_text
    assert report.bodies_merged == 1


def test_apply_merges_skips_default_hint_memo(tmp_path: Path) -> None:
    """skeleton 初期 hint しかない統合元は memo 転記しない(雑音追加防止)"""
    cfg = _mk_cfg(tmp_path)
    _mk_skeleton(cfg.vault, "人物", "アイテックス")  # default hint のみ
    _mk_skeleton(cfg.vault, "人物", "アイタックス")

    entries = [
        skeleton_merge.AliasEntry(
            category="人物", source="アイテックス", target="アイタックス"
        )
    ]
    plans = skeleton_merge.plan_merges(entries, cfg)
    report = skeleton_merge.apply_merges(plans, cfg, dry_run=False)

    assert report.bodies_merged == 0
    tgt_text = (cfg.vault / "人物" / "アイタックス.md").read_text(encoding="utf-8")
    assert "## 統合元:" not in tgt_text


def test_apply_merges_idempotent_memo_section(tmp_path: Path) -> None:
    """同じ alias を 2 回 apply しても memo セクションが重複しない"""
    cfg = _mk_cfg(tmp_path)
    _mk_skeleton(cfg.vault, "人物", "A", memo="メモ本文")
    _mk_skeleton(cfg.vault, "人物", "B")

    entries = [skeleton_merge.AliasEntry(category="人物", source="A", target="B")]
    plans = skeleton_merge.plan_merges(entries, cfg)
    skeleton_merge.apply_merges(plans, cfg, dry_run=False)

    # 2 回目: source 既に消えてるので no-op (plan_merges で skip 理由が入る)
    _mk_skeleton(cfg.vault, "人物", "A", memo="メモ本文 v2")
    plans2 = skeleton_merge.plan_merges(entries, cfg)
    skeleton_merge.apply_merges(plans2, cfg, dry_run=False)

    tgt_text = (cfg.vault / "人物" / "B.md").read_text(encoding="utf-8")
    # 1 セクションだけ(重複追記しない)
    assert tgt_text.count("## 統合元: A のメモ") == 1


# -------------------- format helpers (smoke) --------------------


def test_format_plan_report_smoke(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    _mk_skeleton(cfg.vault, "人物", "A")
    _mk_skeleton(cfg.vault, "人物", "B")
    entries = [skeleton_merge.AliasEntry(category="人物", source="A", target="B")]
    plans = skeleton_merge.plan_merges(entries, cfg)
    out = skeleton_merge.format_plan_report(plans)
    assert "人物" in out and "A" in out and "B" in out


def test_format_apply_report_smoke() -> None:
    report = skeleton_merge.ApplyReport(
        plans_applied=2, plans_skipped=1, wikilinks_rewritten=5,
        files_rewritten=3, sources_deleted=2, sources_renamed=1, bodies_merged=1,
    )
    out = skeleton_merge.format_apply_report(report)
    assert "適用 2" in out
    assert "wikilink 書き換え: 5" in out
