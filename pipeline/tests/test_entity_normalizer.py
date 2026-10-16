"""entity_normalizer の単体テスト。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import entity_normalizer
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


def _mk_skeleton(vault: Path, category: str, name: str) -> None:
    """vault/<category>/<name>.md を作成。"""
    d = vault / category
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text("# " + name + "\n", encoding="utf-8")


# -------------------- normalize --------------------


def test_normalize_strips_honorifics() -> None:
    assert entity_normalizer.normalize("瑞穂さん") == "瑞穂"
    assert entity_normalizer.normalize("田中様") == "田中"
    assert entity_normalizer.normalize("山田氏") == "山田"
    assert entity_normalizer.normalize("佐藤先生") == "佐藤"
    assert entity_normalizer.normalize("健太くん") == "健太"
    assert entity_normalizer.normalize("花子ちゃん") == "花子"


def test_normalize_does_not_overstrip_short_names() -> None:
    """`さん` だけの入力など、敬称 strip で空になる場合は strip しない。"""
    assert entity_normalizer.normalize("さん") == "さん"
    assert entity_normalizer.normalize("様") == "様"


def test_normalize_nfkc_full_to_half() -> None:
    """全角英数は半角に正規化される。"""
    # 全角の "ABC" → 半角 "ABC"
    assert entity_normalizer.normalize("ABC社") == "ABC社"


def test_normalize_keeps_whitespace_inside() -> None:
    """前後 strip のみ、内部の空白は維持。"""
    assert entity_normalizer.normalize("  山田 太郎  ") == "山田 太郎"


# -------------------- find_canonical --------------------


def test_find_canonical_exact_match() -> None:
    assert (
        entity_normalizer.find_canonical("瑞穂さん", ["瑞穂さん", "田中"])
        == "瑞穂さん"
    )


def test_find_canonical_normalized_match_honorific() -> None:
    """新規 "瑞穂" → 既存 "瑞穂さん" を canonical として返す。"""
    assert (
        entity_normalizer.find_canonical("瑞穂", ["瑞穂さん", "田中"])
        == "瑞穂さん"
    )


def test_find_canonical_reverse_honorific_match() -> None:
    """新規 "瑞穂さん" → 既存 "瑞穂" にも match させる。"""
    assert (
        entity_normalizer.find_canonical("瑞穂さん", ["瑞穂", "田中"])
        == "瑞穂"
    )


def test_find_canonical_no_match() -> None:
    assert (
        entity_normalizer.find_canonical("新規さん", ["瑞穂", "田中"])
        is None
    )


def test_find_canonical_empty_input() -> None:
    assert entity_normalizer.find_canonical("", ["瑞穂"]) is None
    assert entity_normalizer.find_canonical("   ", ["瑞穂"]) is None


# -------------------- normalize_entity_list --------------------


def test_normalize_entity_list_uses_canonical() -> None:
    out = entity_normalizer.normalize_entity_list(
        ["瑞穂さん", "新人", "田中"], existing=["瑞穂", "田中"]
    )
    # 瑞穂さん → 瑞穂 (canonical 解決), 新人 → そのまま, 田中 → そのまま
    assert out == ["瑞穂", "新人", "田中"]


def test_normalize_entity_list_dedup_after_canonical() -> None:
    """正規化後の重複は除去。"""
    out = entity_normalizer.normalize_entity_list(
        ["瑞穂さん", "瑞穂", "瑞穂様"], existing=["瑞穂"]
    )
    assert out == ["瑞穂"]


def test_normalize_entity_list_keeps_order() -> None:
    out = entity_normalizer.normalize_entity_list(
        ["田中", "瑞穂さん", "山田"], existing=["瑞穂"]
    )
    assert out == ["田中", "瑞穂", "山田"]


def test_normalize_entity_list_skips_empty() -> None:
    out = entity_normalizer.normalize_entity_list(
        ["瑞穂", "", "  ", "田中"], existing=[]
    )
    assert out == ["瑞穂", "田中"]


# -------------------- normalize_structured --------------------


def test_normalize_structured_full_flow(tmp_path: Path) -> None:
    """既存 skeleton 「瑞穂」「リアックス」がある時に、新規 「瑞穂さん」
    「リアックスさん」を含む structured を渡すと canonical に置換される。"""
    cfg = _mk_cfg(tmp_path)
    _mk_skeleton(cfg.vault, "人物", "瑞穂")
    _mk_skeleton(cfg.vault, "人物", "リアックス")
    _mk_skeleton(cfg.vault, "トピック", "ユニット交換")
    _mk_skeleton(cfg.vault, "場所", "総合体育館")

    structured = {
        "contexts": [
            {
                "title": "商談",
                "counterpart": ["瑞穂さん", "リアックスさん", "新人"],
                "topics": ["ユニット交換", "新トピック"],
                "locations": ["総合体育館"],
            }
        ]
    }
    out = entity_normalizer.normalize_structured(structured, cfg)
    ctx = out["contexts"][0]
    assert ctx["counterpart"] == ["瑞穂", "リアックス", "新人"]
    assert ctx["topics"] == ["ユニット交換", "新トピック"]
    assert ctx["locations"] == ["総合体育館"]
    # 原本不変
    assert structured["contexts"][0]["counterpart"] == [
        "瑞穂さん",
        "リアックスさん",
        "新人",
    ]


def test_normalize_structured_no_vault_yet(tmp_path: Path) -> None:
    """vault フォルダがまだ無い場合は新規扱いで素通り。"""
    cfg = _mk_cfg(tmp_path)
    structured = {
        "contexts": [{"counterpart": ["瑞穂さん"], "topics": [], "locations": []}]
    }
    out = entity_normalizer.normalize_structured(structured, cfg)
    # vault 配下が無いので何もマッチせず原本のまま
    assert out["contexts"][0]["counterpart"] == ["瑞穂さん"]


def test_normalize_structured_empty_contexts(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path)
    structured = {"contexts": []}
    out = entity_normalizer.normalize_structured(structured, cfg)
    assert out == structured


def test_normalize_structured_missing_keys(tmp_path: Path) -> None:
    """context に counterpart/topics/locations が無くてもエラーにならない。"""
    cfg = _mk_cfg(tmp_path)
    structured = {"contexts": [{"title": "t", "summary": "s", "importance": 3}]}
    out = entity_normalizer.normalize_structured(structured, cfg)
    assert out["contexts"][0]["title"] == "t"
