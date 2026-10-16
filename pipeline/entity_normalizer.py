"""Phase 3 前段: エンティティ名寄せ。

Claude が抽出する人物名・トピック・場所名には表記揺れがある:
- 敬称付き / 無し: "瑞穂さん" vs "瑞穂"
- 全角/半角揺れ: "リアックス" vs "リアックス" (NFKC で正規化)

既存の Vault skeleton ファイル名を canonical とみなし、新規抽出結果が
正規化すると既存と一致する場合は canonical 名に置換する。これで
重複 skeleton (`瑞穂.md` と `瑞穂さん.md` が別物として作られる) を防ぐ。

今回入れていないが将来必要なケース:
- 別表記 (script): "ミズホ" vs "瑞穂" vs "みずほ" → AI judge or
  手動 alias テーブルが必要
- typo: "アイタックス" vs "アイテックス" → edit distance + 慎重な
  しきい値設定が必要(過剰マージ防止)
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

from config import Config


# 敬称マッチは長い接尾辞を先に試す(「ちゃん」を「ん」より先に剥がしたい)。
_HONORIFIC_SUFFIXES: tuple[str, ...] = (
    "ちゃん",
    "くん",
    "さん",
    "先生",
    "様",
    "氏",
    "君",
)


def _strip_honorific(name: str) -> str:
    """末尾の敬称を 1 個だけ取り除く。
    残りが空になるなら strip しない(`さん` だけの入力を空にしない)。"""
    for suffix in _HONORIFIC_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def normalize(name: str) -> str:
    """比較用の正規形を返す。

    - 前後空白除去
    - NFKC 正規化(全角英数→半角、半角カナ→全角等)
    - 敬称末尾 strip"""
    s = unicodedata.normalize("NFKC", name.strip())
    s = _strip_honorific(s)
    return s


def _scan_existing(category_dir: Path) -> list[str]:
    """vault/人物/, vault/トピック/, vault/場所/ 配下の .md ファイル名
    (拡張子除く) のリスト。skeleton マーカー有無は問わない(手書きのノートも
    canonical として尊重)。"""
    if not category_dir.exists() or not category_dir.is_dir():
        return []
    return sorted(p.stem for p in category_dir.glob("*.md"))


def find_canonical(name: str, existing: list[str]) -> str | None:
    """existing の中で name と同一エンティティを指すものを返す。

    1. 完全一致(正規化なし)が最優先
    2. 正規化後一致(敬称 strip / NFKC 後同じ)
    無ければ None(新規エンティティ扱い)。"""
    if not name.strip():
        return None
    if name in existing:
        return name
    n = normalize(name)
    if not n:
        return None
    for cand in existing:
        if normalize(cand) == n:
            return cand
    return None


def normalize_entity_list(
    names: list[str], existing: list[str]
) -> list[str]:
    """エンティティ名リストを既存 skeleton に対して正規化。

    - 既存と一致(canonical 解決)した名前は canonical 名に置換
    - 既存に無い名前は前後空白を取り除いてそのまま残す(新規 skeleton)
    - リスト内重複は除去(出現順保持)
    - 空文字・空白のみは除外"""
    out: list[str] = []
    seen: set[str] = set()
    for raw in names:
        if not raw or not str(raw).strip():
            continue
        s = str(raw).strip()
        canonical = find_canonical(s, existing) or s
        if canonical not in seen:
            seen.add(canonical)
            out.append(canonical)
    return out


def normalize_structured(structured: dict, cfg: Config) -> dict:
    """structure_transcript の結果 (`{"contexts": [...]}`) を正規化。

    contexts[i].counterpart / topics / locations を、各カテゴリの既存
    skeleton ファイル名に対して名寄せする。新しい dict を返す(原本不変)。

    vault が無い / カテゴリフォルダが無い場合は新規扱いで素通し。"""
    contexts = structured.get("contexts") or []
    if not contexts:
        return structured

    existing_persons = _scan_existing(cfg.vault / "人物")
    existing_topics = _scan_existing(cfg.vault / "トピック")
    existing_locations = _scan_existing(cfg.vault / "場所")

    out_contexts: list[dict] = []
    for ctx in contexts:
        new_ctx = dict(ctx)
        if ctx.get("counterpart"):
            new_ctx["counterpart"] = normalize_entity_list(
                ctx["counterpart"], existing_persons
            )
        if ctx.get("topics"):
            new_ctx["topics"] = normalize_entity_list(
                ctx["topics"], existing_topics
            )
        if ctx.get("locations"):
            new_ctx["locations"] = normalize_entity_list(
                ctx["locations"], existing_locations
            )
        out_contexts.append(new_ctx)

    return {**structured, "contexts": out_contexts}
