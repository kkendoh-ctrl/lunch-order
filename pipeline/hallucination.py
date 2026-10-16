"""ハルシネーション後処理。

WhisperX (faster-whisper) の小音量・断続音声に対する繰り返しハルシネーション
("ご視聴ありがとうございました", "うん うん うん..." 等) を検知して
セグメント単位で drop マークを付ける。

faster-whisper の `condition_on_previous_text=False` と温度フォールバックで
8 割は抑制できているが、残った定型句・連発系を最終段で掃除する。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# Whisper の学習データ (YouTube subtitle) 由来の頻出定型句。
# セグメント全体がこの句で占められていたら drop。
_DEFAULT_BLACKLIST: tuple[str, ...] = (
    "ご視聴ありがとうございました",
    "ご視聴ありがとうございます",
    "ご視聴いただきありがとうございました",
    "ご覧いただきありがとうございました",
    "チャンネル登録",
    "高評価",
    "おやすみなさい",
)


def load_blacklist(extra_path: Path | None) -> tuple[str, ...]:
    """デフォルト + 外部ファイル (1 行 1 句、`#` でコメント) を合成。

    .env で `HALLUCINATION_DROP_BLACKLIST_PATH` を指定すれば、業務固有の
    定型句(社名連呼等)を Vault 外で追加できる。"""
    items: list[str] = list(_DEFAULT_BLACKLIST)
    if extra_path is None or not extra_path.exists():
        return tuple(items)
    for line in extra_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            items.append(s)
    return tuple(dict.fromkeys(items))  # 重複除去 + 入力順保持


def _matches_blacklist(text: str, blacklist: tuple[str, ...]) -> str | None:
    """セグメントが「ほぼ全部 blacklist の定型句」なら、その句を返す。

    完全一致だけでなく、句が含まれていて残りが極短い場合も検知
    (「ご視聴... ご視聴...」のような連発も拾う)。"""
    s = text.strip()
    for phrase in blacklist:
        if phrase not in s:
            continue
        remaining = s.replace(phrase, "").strip()
        # 句以外がほぼ空 (< 8 文字) ならハルシネーション扱い
        if len(remaining) <= 8:
            return phrase
    return None


def _max_token_repeat(text: str) -> int:
    """同一トークン(空白区切り)の最大連続回数。"""
    tokens = text.split()
    if not tokens:
        return 0
    streak = 1
    best = 1
    for i in range(1, len(tokens)):
        if tokens[i] == tokens[i - 1]:
            streak += 1
            if streak > best:
                best = streak
        else:
            streak = 1
    return best


def _max_ngram_repeat(
    text: str, n_min: int = 2, n_max: int = 5
) -> tuple[int, int]:
    """N-gram (n=n_min..n_max) の最大連続繰り返し回数と、その n。

    例: "あ い う あ い う あ い う" → (3, 3) (3-gram が 3 連発)。"""
    tokens = text.split()
    best_count = 0
    best_n = 0
    for n in range(n_min, n_max + 1):
        if len(tokens) < n * 2:
            continue
        for start in range(len(tokens) - n + 1):
            ngram = tuple(tokens[start : start + n])
            count = 1
            pos = start + n
            while (
                pos + n <= len(tokens)
                and tuple(tokens[pos : pos + n]) == ngram
            ):
                count += 1
                pos += n
            if count > best_count:
                best_count = count
                best_n = n
    return best_count, best_n


def _max_substring_repeat(
    text: str, n_min: int = 2, n_max: int = 4
) -> tuple[int, int]:
    """空白を取り除いた本文中の連続部分文字列の最大繰り返し回数と長さ。

    「そのうちのうちのうちのうち」のような空白なし系パターン用。"""
    s = "".join(text.split())  # 空白除去
    best_count = 0
    best_n = 0
    for n in range(n_min, n_max + 1):
        if len(s) < n * 2:
            continue
        for start in range(len(s) - n + 1):
            substr = s[start : start + n]
            count = 1
            pos = start + n
            while pos + n <= len(s) and s[pos : pos + n] == substr:
                count += 1
                pos += n
            if count > best_count:
                best_count = count
                best_n = n
    return best_count, best_n


@dataclass(frozen=True)
class Verdict:
    is_hallucination: bool
    reason: str  # "blacklist:..." / "token_repeat:N" / "ngram_repeat:CxN" / "substr_repeat:CxN"


def detect(
    text: str,
    *,
    blacklist: tuple[str, ...] = _DEFAULT_BLACKLIST,
    token_streak_threshold: int = 5,
    ngram_streak_threshold: int = 4,
    substr_streak_threshold: int = 6,
) -> Verdict:
    """セグメント text をハルシネーション判定。優先度はブラックリスト >
    同一トークン > N-gram > 空白なし部分文字列。"""
    if not text.strip():
        return Verdict(False, "")

    phrase = _matches_blacklist(text, blacklist)
    if phrase is not None:
        return Verdict(True, f"blacklist:{phrase}")

    token_streak = _max_token_repeat(text)
    if token_streak >= token_streak_threshold:
        return Verdict(True, f"token_repeat:{token_streak}")

    ngram_count, ngram_n = _max_ngram_repeat(text)
    if ngram_count >= ngram_streak_threshold:
        return Verdict(True, f"ngram_repeat:{ngram_count}x{ngram_n}")

    substr_count, substr_n = _max_substring_repeat(text)
    if substr_count >= substr_streak_threshold:
        return Verdict(True, f"substr_repeat:{substr_count}x{substr_n}")

    return Verdict(False, "")


def filter_segments(
    segments: list[dict],
    *,
    blacklist: tuple[str, ...] = _DEFAULT_BLACKLIST,
    token_streak_threshold: int = 5,
    ngram_streak_threshold: int = 4,
    substr_streak_threshold: int = 6,
) -> tuple[list[dict], int]:
    """segments を走査して、ハルシネーション判定されたセグメントの text を
    `[ハルシネーション drop: <reason>]` に置換、original_text を残す。

    タイムスタンプ・speaker 等の他フィールドは保持。drop しても segment
    リストの長さは変わらない(下流の集約で順序保証のため)。

    返り値は (filtered_segments, drop_count)。"""
    out: list[dict] = []
    drop_count = 0
    for seg in segments:
        text = str(seg.get("text") or "")
        v = detect(
            text,
            blacklist=blacklist,
            token_streak_threshold=token_streak_threshold,
            ngram_streak_threshold=ngram_streak_threshold,
            substr_streak_threshold=substr_streak_threshold,
        )
        new_seg = dict(seg)
        if v.is_hallucination:
            new_seg["original_text"] = text
            new_seg["text"] = f"[ハルシネーション drop: {v.reason}]"
            new_seg["dropped_reason"] = v.reason
            drop_count += 1
        out.append(new_seg)
    return out, drop_count
