"""hallucination.py の純粋関数テスト。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import hallucination


# -------------------- detect: blacklist --------------------


def test_detect_blacklist_youtube_phrase() -> None:
    v = hallucination.detect("ご視聴ありがとうございました")
    assert v.is_hallucination
    assert "blacklist:" in v.reason


def test_detect_blacklist_repeated_phrase() -> None:
    """同じ blacklist 句が複数回繰り返されているケースも detect。"""
    text = "ご視聴ありがとうございました ご視聴ありがとうございました"
    v = hallucination.detect(text)
    assert v.is_hallucination


def test_detect_blacklist_with_short_remainder_ok() -> None:
    """句 + 少しの他テキスト (8 文字以内) は drop 対象。"""
    text = "ご視聴ありがとうございました はい"
    v = hallucination.detect(text)
    assert v.is_hallucination


def test_detect_blacklist_with_long_remainder_not_dropped() -> None:
    """句が混じっていても、業務情報が大量に含まれていたら drop しない。"""
    text = (
        "本日の議題は券売機の更新計画について議論しました。"
        "ご視聴ありがとうございました。"
        "次回はキャッシュレス対応について検討します。"
    )
    v = hallucination.detect(text)
    assert not v.is_hallucination


# -------------------- detect: token repeat --------------------


def test_detect_token_repeat_yes() -> None:
    v = hallucination.detect("うん うん うん うん うん")
    assert v.is_hallucination
    assert "token_repeat:5" in v.reason


def test_detect_token_repeat_under_threshold_no() -> None:
    """4 連続なら通す(会話で起こり得る)。"""
    v = hallucination.detect("うん うん うん うん")
    assert not v.is_hallucination


def test_detect_token_repeat_custom_threshold() -> None:
    """threshold=3 に下げれば 3 連続でも検知。"""
    v = hallucination.detect(
        "ビザ ビザ ビザ", token_streak_threshold=3
    )
    assert v.is_hallucination


# -------------------- detect: n-gram repeat --------------------


def test_detect_ngram_repeat_2gram() -> None:
    """2 トークン phrase の 4 連発。"""
    v = hallucination.detect(
        "アリハビリ 致 アリハビリ 致 アリハビリ 致 アリハビリ 致"
    )
    assert v.is_hallucination
    # 2x4 か、または "アリハビリ" 単体の token_repeat が先に発火
    assert v.reason.startswith(("ngram_repeat:", "token_repeat:"))


def test_detect_ngram_3gram_repeat() -> None:
    """3 トークン phrase の連発。"""
    text = "あ い う あ い う あ い う あ い う"
    v = hallucination.detect(text)
    assert v.is_hallucination


# -------------------- detect: substring repeat (no-space) --------------------


def test_detect_substring_repeat_no_space() -> None:
    """「のうちのうちのうち...」のような空白なし反復。"""
    text = "そのうちのうちのうちのうちのうちのうちのうちのうち"
    v = hallucination.detect(text)
    assert v.is_hallucination
    assert v.reason.startswith("substr_repeat:")


def test_detect_substring_repeat_short_text_no() -> None:
    """短すぎる場合は誤検知しない。"""
    v = hallucination.detect("そのうちの")
    assert not v.is_hallucination


# -------------------- detect: normal text passes through --------------------


def test_detect_normal_japanese_text() -> None:
    """普通の業務発話は通す。"""
    text = (
        "本日は券売機の更新計画について議論しました。"
        "2.5 ヶ月後にキャッシュレス対応ユニットへ交換する方針です。"
    )
    v = hallucination.detect(text)
    assert not v.is_hallucination
    assert v.reason == ""


def test_detect_empty_text() -> None:
    assert not hallucination.detect("").is_hallucination
    assert not hallucination.detect("   ").is_hallucination


# -------------------- filter_segments --------------------


def test_filter_segments_replaces_dropped() -> None:
    segments = [
        {"start": 0.0, "end": 5.0, "text": "業務の話"},
        {"start": 5.0, "end": 10.0, "text": "うん うん うん うん うん うん"},
        {"start": 10.0, "end": 15.0, "text": "ご視聴ありがとうございました"},
    ]
    out, drops = hallucination.filter_segments(segments)
    assert drops == 2
    assert out[0]["text"] == "業務の話"
    # drop されたセグメントはマーカーに置換、original_text が残る
    assert out[1]["text"].startswith("[ハルシネーション drop:")
    assert out[1]["original_text"] == "うん うん うん うん うん うん"
    assert "token_repeat" in out[1]["dropped_reason"]
    assert out[2]["text"].startswith("[ハルシネーション drop:")
    assert "blacklist:" in out[2]["dropped_reason"]


def test_filter_segments_preserves_timing_and_speaker() -> None:
    segments = [
        {
            "start": 5.0,
            "end": 10.0,
            "text": "ご視聴ありがとうございました",
            "speaker": "SPEAKER_01",
        }
    ]
    out, drops = hallucination.filter_segments(segments)
    assert drops == 1
    assert out[0]["start"] == 5.0
    assert out[0]["end"] == 10.0
    assert out[0]["speaker"] == "SPEAKER_01"


def test_filter_segments_no_drops_passes_through() -> None:
    segments = [
        {"start": 0.0, "end": 5.0, "text": "業務の話"},
        {"start": 5.0, "end": 10.0, "text": "次の議題"},
    ]
    out, drops = hallucination.filter_segments(segments)
    assert drops == 0
    assert out == segments
    # 原本に dropped_reason が混入していないことを確認
    for seg in out:
        assert "dropped_reason" not in seg
        assert "original_text" not in seg


# -------------------- load_blacklist --------------------


def test_load_blacklist_default_only(tmp_path: Path) -> None:
    bl = hallucination.load_blacklist(None)
    assert "ご視聴ありがとうございました" in bl


def test_load_blacklist_extra_file(tmp_path: Path) -> None:
    """外部ファイルで業務固有の定型句を追加できる。"""
    p = tmp_path / "blacklist.txt"
    p.write_text(
        "# コメント行は無視\n"
        "弊社の社訓を申し上げます\n"
        "本日のニュースをお伝えします\n"
        "\n"  # 空行も無視
        "ご視聴ありがとうございました\n",  # 既存と重複してもOK
        encoding="utf-8",
    )
    bl = hallucination.load_blacklist(p)
    assert "弊社の社訓を申し上げます" in bl
    assert "本日のニュースをお伝えします" in bl
    # 重複は除去されている
    assert bl.count("ご視聴ありがとうございました") == 1


def test_load_blacklist_missing_file_returns_default(tmp_path: Path) -> None:
    bl = hallucination.load_blacklist(tmp_path / "nonexistent.txt")
    assert "ご視聴ありがとうございました" in bl
