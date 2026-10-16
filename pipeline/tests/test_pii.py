"""pii.py のテスト(Claude/WhisperX 不要)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

import pii
from config import Config


# -------------------- 正規表現ルール --------------------


def test_mask_email() -> None:
    m = pii.PIIMasker()
    r = m.mask("連絡先は taro@example.com です")
    assert r.text == "連絡先は [メール] です"
    assert r.replacements == 1


def test_mask_email_plus_alias() -> None:
    m = pii.PIIMasker()
    r = m.mask("メールは taro+work@sub.example.co.jp")
    assert "[メール]" in r.text
    assert "taro+work" not in r.text


def test_mask_phone_japanese() -> None:
    m = pii.PIIMasker()
    # 日本語テキストの真ん中(`\b` が効かない位置)でも当たる
    r = m.mask("お電話は090-1234-5678まで")
    assert r.text == "お電話は[電話番号]まで"
    assert r.replacements == 1


def test_mask_phone_landline() -> None:
    m = pii.PIIMasker()
    r = m.mask("市役所(03-1234-5678)に確認")
    assert "[電話番号]" in r.text
    assert "03-" not in r.text


def test_mask_postal_code() -> None:
    m = pii.PIIMasker()
    r = m.mask("住所は279-0001の方です")
    assert "[郵便番号]" in r.text
    assert "279-" not in r.text


def test_mask_application_number_7digits() -> None:
    m = pii.PIIMasker()
    r = m.mask("申請番号1234567で照会")
    assert "[申請番号]" in r.text
    assert "1234567" not in r.text


def test_mask_credit_card() -> None:
    m = pii.PIIMasker()
    r = m.mask("カード1234-5678-9012-3456の件")
    assert "[カード番号]" in r.text
    assert "1234-" not in r.text


def test_mask_credit_card_no_dash() -> None:
    m = pii.PIIMasker()
    r = m.mask("1234567890123456 が請求された")
    # ハイフンなし 16 桁もカード扱いされる
    assert "[カード番号]" in r.text


def test_mask_does_not_eat_short_digits() -> None:
    """通常の年・人数などはマスクしない。"""
    m = pii.PIIMasker()
    r = m.mask("2026 年に 50 人が参加")
    assert r.text == "2026 年に 50 人が参加"
    assert r.replacements == 0


def test_mask_multiple_in_one_text() -> None:
    m = pii.PIIMasker()
    r = m.mask("田中(090-1111-2222 / tanaka@example.com)に連絡")
    assert "[電話番号]" in r.text
    assert "[メール]" in r.text
    assert r.replacements == 2


def test_mask_disabled() -> None:
    m = pii.PIIMasker(enabled=False)
    r = m.mask("090-1234-5678")
    assert r.text == "090-1234-5678"
    assert r.replacements == 0


def test_mask_empty_string() -> None:
    m = pii.PIIMasker()
    r = m.mask("")
    assert r.text == ""
    assert r.replacements == 0


# -------------------- ユーザー辞書 --------------------


def test_dict_rule_replaces_substring() -> None:
    m = pii.PIIMasker(dict_rules={"田中花子": "[個人A]"})
    r = m.mask("田中花子さんから連絡")
    assert "[個人A]" in r.text
    assert "田中花子" not in r.text


def test_dict_rule_longest_match_first() -> None:
    """長いキーが先に当たり、短いキーが部分文字列を壊さない。"""
    m = pii.PIIMasker(
        dict_rules={"田中": "[姓のみ]", "田中花子": "[フルネーム]"}
    )
    r = m.mask("田中花子と田中太郎")
    # 田中花子 → [フルネーム] が先、その後「田中太郎」の田中だけ [姓のみ] に
    assert "[フルネーム]" in r.text
    assert "田中太郎" not in r.text
    assert "[姓のみ]太郎" in r.text


def test_dict_rule_with_regex_combined() -> None:
    m = pii.PIIMasker(dict_rules={"田中花子": "[個人A]"})
    r = m.mask("田中花子(090-1111-2222)")
    assert "[個人A]" in r.text
    assert "[電話番号]" in r.text


def test_dict_rule_empty_key_ignored() -> None:
    m = pii.PIIMasker(dict_rules={"": "[X]", "田中": "[個人]"})
    r = m.mask("田中さん")
    assert "[個人]" in r.text


# -------------------- YAML 辞書ロード --------------------


def test_load_dict_missing_file(tmp_path: Path) -> None:
    assert pii._load_dict(tmp_path / "nonexistent.yaml") == {}
    assert pii._load_dict(None) == {}


def test_load_dict_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    assert pii._load_dict(p) == {}


def test_load_dict_valid(tmp_path: Path) -> None:
    p = tmp_path / "pii_dict.yaml"
    p.write_text(
        "田中花子: '[個人A]'\n"
        "090-1234-5678: '[電話番号]'\n"
        "山田: null\n",
        encoding="utf-8",
    )
    out = pii._load_dict(p)
    assert out["田中花子"] == "[個人A]"
    assert out["090-1234-5678"] == "[電話番号]"
    assert out["山田"] == "[マスク]"  # null は [マスク] に


def test_load_dict_rejects_non_dict(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("- list\n- form\n", encoding="utf-8")
    with pytest.raises(ValueError):
        pii._load_dict(p)


# -------------------- transcript マスク --------------------


def _transcript() -> dict:
    return {
        "audio_path": "/tmp/x.m4a",
        "duration_s": 10.0,
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "田中(090-1234-5678)から"},
            {"start": 2.5, "end": 5.0, "text": "tanaka@example.com にメール"},
        ],
        "text": "田中(090-1234-5678)から tanaka@example.com にメール",
    }


def test_mask_transcript_full(tmp_path: Path) -> None:
    masker = pii.PIIMasker(dict_rules={"田中": "[個人A]"})
    new, n = pii.mask_transcript(_transcript(), masker)
    # 2 segments + 1 連結 text を順に処理:
    # seg0: 田中 + 090-... = 2 / seg1: tanaka@... = 1
    # text: 田中 + 090-... + tanaka@... = 3
    assert n == 6
    # 元 dict は変更されていない
    original = _transcript()
    assert original["segments"][0]["text"] == "田中(090-1234-5678)から"
    # 新 dict はマスクされている
    assert new["segments"][0]["text"] == "[個人A]([電話番号])から"
    assert new["segments"][1]["text"] == "[メール] にメール"
    assert "[個人A]" in new["text"]
    assert "[電話番号]" in new["text"]


def test_mask_transcript_no_change_when_disabled() -> None:
    masker = pii.PIIMasker(enabled=False)
    new, n = pii.mask_transcript(_transcript(), masker)
    assert n == 0
    # disabled なら元 dict をそのまま返す(コピーしない)
    assert new is _transcript.__call__() or new == _transcript()


def test_mask_transcript_handles_missing_segments() -> None:
    masker = pii.PIIMasker()
    new, n = pii.mask_transcript({"text": "090-1234-5678"}, masker)
    assert new["text"] == "[電話番号]"
    assert n == 1


# -------------------- Config 連携 --------------------


def _mk_cfg(
    tmp_path: Path, *, enabled: bool = True, dict_path: Path | None = None
) -> Config:
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
        pii_mask_enabled=enabled,
        pii_dict_path=dict_path,
        pii_allowlist_path=None,
    )


def test_from_config_enabled_with_dict(tmp_path: Path) -> None:
    dict_path = tmp_path / "pii_dict.yaml"
    dict_path.write_text("山田: '[個人B]'\n", encoding="utf-8")
    cfg = _mk_cfg(tmp_path, enabled=True, dict_path=dict_path)
    masker = pii.PIIMasker.from_config(cfg)
    assert masker.enabled
    r = masker.mask("山田さんに090-0000-0000で連絡")
    assert "[個人B]" in r.text
    assert "[電話番号]" in r.text


def test_from_config_disabled(tmp_path: Path) -> None:
    cfg = _mk_cfg(tmp_path, enabled=False)
    masker = pii.PIIMasker.from_config(cfg)
    assert not masker.enabled
    r = masker.mask("090-1234-5678")
    assert r.text == "090-1234-5678"


def test_from_config_no_dict_file(tmp_path: Path) -> None:
    """dict_path 指定なし → regex だけ走る。"""
    cfg = _mk_cfg(tmp_path, enabled=True, dict_path=None)
    masker = pii.PIIMasker.from_config(cfg)
    assert masker.enabled
    r = masker.mask("090-1234-5678")
    assert "[電話番号]" in r.text
