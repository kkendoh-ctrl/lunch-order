"""既存重複 skeleton のマージ (one-off cleanup スクリプト用)。

entity_normalizer は「これから新規生成される skeleton」の重複を防ぐが、
過去ラウンドで既に生まれてしまった重複 (アイテックス ⇄ アイタックス、
リアックス ⇄ リアックスさん 等) は救えない。それを後から手動 alias テーブルで
統合するための仕組み。

入力: YAML/JSON 形式の alias テーブル
出力: 統合元 skeleton 削除 + vault 内 wikilink 全置換 + 統合先 skeleton への
      メモ転記

vault 全体を破壊的に書き換えるので、`--dry-run` (CLI default) で必ず先に
確認させる設計。本実行は `--apply` を明示。
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from config import Config


# alias テーブル上のカテゴリ名。entity_normalizer / aggregator と揃える。
CATEGORIES: tuple[str, ...] = ("人物", "トピック", "場所")

_SKELETON_MARKER = "<!-- auto-skeleton -->"

# `[[...]]` を 1 個拾う非貪欲マッチ。改行・他の `[`/`]` は跨がない。
_WIKILINK_RE = re.compile(r"\[\[([^\[\]\n]+?)\]\]")


# -------------------- データクラス --------------------


@dataclass(frozen=True)
class AliasEntry:
    """1 件の統合指示 (source を target にマージ)。"""

    category: str
    source: str
    target: str

    def __post_init__(self) -> None:
        if self.source == self.target:
            raise ValueError(
                f"alias の source と target が同じ: {self.category}/{self.source}"
            )


@dataclass
class WikilinkRewrite:
    """1 ファイル内の wikilink 書き換え計画。"""

    path: Path
    before: str
    after: str
    occurrences: int  # before → after に書き換える出現回数


@dataclass
class MergePlan:
    """1 件の alias について「何が起きるか」を網羅する計画。"""

    entry: AliasEntry
    source_path: Path
    target_path: Path
    source_exists: bool
    target_exists: bool
    source_is_skeleton: bool
    target_is_skeleton: bool
    rewrites: list[WikilinkRewrite] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # warning / skip 理由


@dataclass
class ApplyReport:
    """実適用結果。"""

    plans_applied: int = 0
    plans_skipped: int = 0
    files_rewritten: int = 0
    wikilinks_rewritten: int = 0
    sources_deleted: int = 0
    sources_renamed: int = 0  # target が無くてリネームしたケース
    bodies_merged: int = 0  # 統合元の手書きメモを統合先に転記したケース
    errors: list[str] = field(default_factory=list)


# -------------------- alias テーブル読み込み --------------------


def load_alias_table(path: Path) -> list[AliasEntry]:
    """YAML/JSON ファイル → AliasEntry のリスト。

    期待フォーマット:
        人物:
          アイテックス: アイタックス      # アイテックス を アイタックス に統合
          リアックスさん: リアックス
        トピック:
          バーコードリーダーシステム: バーコードリーダー
        場所: {}

    トップレベルのキーは CATEGORIES (`人物`/`トピック`/`場所`) のみ受理。
    未知カテゴリはエラーで弾く(typo 防止)。"""
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(
            f"alias ファイルのトップレベルは dict にしてください: {path}"
        )

    entries: list[AliasEntry] = []
    seen_sources: set[tuple[str, str]] = set()
    for category, mapping in data.items():
        if category not in CATEGORIES:
            raise ValueError(
                f"未知カテゴリ {category!r}。許可: {CATEGORIES}"
            )
        if mapping is None:
            continue
        if not isinstance(mapping, dict):
            raise ValueError(
                f"{category} の値は source: target の dict にしてください "
                f"(現在: {type(mapping).__name__})"
            )
        for source, target in mapping.items():
            if not isinstance(source, str) or not isinstance(target, str):
                raise ValueError(
                    f"{category}: {source!r} → {target!r} は str: str のみ"
                )
            src = source.strip()
            tgt = target.strip()
            if not src or not tgt:
                raise ValueError(
                    f"{category} で空文字: {source!r} → {target!r}"
                )
            key = (category, src)
            if key in seen_sources:
                raise ValueError(
                    f"{category}/{src} が複数定義されています"
                )
            seen_sources.add(key)
            entries.append(AliasEntry(category=category, source=src, target=tgt))
    return entries


# -------------------- wikilink 書き換え --------------------


def _wikilink_inner_matches(inner: str, source: str) -> bool:
    """`[[...]]` の `...` 部分が source への参照かを判定。

    マッチする形:
      - `アイテックス`               → match
      - `アイテックス|表示名`         → match (canonical = アイテックス)
      - `人物/アイテックス`           → match
      - `人物/アイテックス|表示名`   → match
      - `アイテックス/別`             → 別ノートなので no match
    """
    canonical = inner
    if "|" in canonical:
        canonical = canonical.split("|", 1)[0]
    canonical = canonical.rsplit("/", 1)[-1]
    return canonical.strip() == source


def _rewrite_wikilink_inner(inner: str, source: str, target: str) -> str:
    """`アイテックス|表示` のような inner を target に差し替える(label/path 維持)。
    マッチしないなら inner をそのまま返す(呼び出し側で _matches を先に確認する想定)。"""
    label_suffix = ""
    if "|" in inner:
        canonical_part, label_suffix = inner.split("|", 1)
        label_suffix = "|" + label_suffix
    else:
        canonical_part = inner

    if "/" in canonical_part:
        prefix, _last = canonical_part.rsplit("/", 1)
        new_canonical = f"{prefix}/{target}"
    else:
        new_canonical = target

    return new_canonical + label_suffix


def rewrite_file_text(text: str, source: str, target: str) -> tuple[str, int]:
    """テキスト中の `[[source]]` 系を `[[target]]` 系に書き換え。
    変更後テキストと、置換回数のタプルを返す。"""
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        inner = m.group(1)
        if not _wikilink_inner_matches(inner, source):
            return m.group(0)
        count += 1
        return "[[" + _rewrite_wikilink_inner(inner, source, target) + "]]"

    new_text = _WIKILINK_RE.sub(repl, text)
    return new_text, count


def _iter_vault_md_files(vault: Path) -> Iterable[Path]:
    """vault 配下の .md を全列挙(skeleton も録音も対象)。
    `_transcripts` などのバイナリ系隔離フォルダは含まれていないが、
    念のため `.git` 系の隠しフォルダは除外する。"""
    for p in vault.rglob("*.md"):
        if any(part.startswith(".") for part in p.parts):
            continue
        yield p


# -------------------- 計画立案 --------------------


def _is_skeleton(path: Path) -> bool:
    """`<!-- auto-skeleton -->` マーカー有無で判定。
    手書きで埋まったノートは skeleton 扱いしない(削除すると本文喪失するため)。"""
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return _SKELETON_MARKER in text


def plan_merges(
    entries: list[AliasEntry], cfg: Config
) -> list[MergePlan]:
    """各 alias について書き換え計画を作る(I/O は read のみ、何も書かない)。"""
    plans: list[MergePlan] = []
    md_files = list(_iter_vault_md_files(cfg.vault))
    for e in entries:
        category_dir = cfg.vault / e.category
        source_path = category_dir / f"{e.source}.md"
        target_path = category_dir / f"{e.target}.md"
        source_exists = source_path.exists()
        target_exists = target_path.exists()
        source_is_skeleton = _is_skeleton(source_path) if source_exists else False
        target_is_skeleton = _is_skeleton(target_path) if target_exists else False

        plan = MergePlan(
            entry=e,
            source_path=source_path,
            target_path=target_path,
            source_exists=source_exists,
            target_exists=target_exists,
            source_is_skeleton=source_is_skeleton,
            target_is_skeleton=target_is_skeleton,
        )

        if not source_exists:
            plan.notes.append(
                f"統合元 skeleton が無いので何もしない: {source_path}"
            )
            plans.append(plan)
            continue

        if source_exists and not source_is_skeleton:
            plan.notes.append(
                "⚠ 統合元が auto-skeleton マーカーを持たない(手書きが入っている "
                "可能性)。本文は統合先に転記し、削除はする"
            )

        for md in md_files:
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            _, count = rewrite_file_text(text, e.source, e.target)
            if count > 0:
                plan.rewrites.append(
                    WikilinkRewrite(
                        path=md,
                        before=e.source,
                        after=e.target,
                        occurrences=count,
                    )
                )

        plans.append(plan)
    return plans


# -------------------- 適用 --------------------


def _extract_skeleton_body(text: str) -> str:
    """skeleton ファイルから手書きメモ部分だけを抽出。

    `<!-- auto-skeleton -->` から `## 関連録音` までの間の `## メモ` セクションを
    拾う。デフォルト hint だけ (`(関係性・所属・連絡先などを追記)` 等) なら
    空文字を返す(転記不要)。"""
    if _SKELETON_MARKER not in text:
        return ""
    after_marker = text.split(_SKELETON_MARKER, 1)[1]

    memo_marker = "## メモ"
    if memo_marker not in after_marker:
        return ""
    after_memo = after_marker.split(memo_marker, 1)[1]

    # 「## 関連録音」「## 統合元」など次の h2 で打ち切る
    next_h2 = re.search(r"^##\s", after_memo, re.MULTILINE)
    if next_h2:
        memo_body = after_memo[: next_h2.start()]
    else:
        memo_body = after_memo

    memo_body = memo_body.strip()
    # デフォルトの「(関係性・所属・連絡先などを追記)」のような hint だけなら空扱い
    if not memo_body:
        return ""
    cleaned = "\n".join(
        line for line in memo_body.splitlines() if line.strip()
    ).strip()
    # 括弧で始まる 1 行ヒントだけのケースを弾く
    if cleaned.startswith("(") and cleaned.endswith(")") and "\n" not in cleaned:
        return ""
    return memo_body


def _append_merged_section(
    target_text: str, source_name: str, memo_body: str
) -> str:
    """統合先ノートに「## 統合元: <source> のメモ」セクションを追記。
    既に同名セクションがある場合は重複追記しない(冪等)。"""
    heading = f"## 統合元: {source_name} のメモ"
    if heading in target_text:
        return target_text
    suffix = "\n" if target_text.endswith("\n") else "\n\n"
    return target_text + suffix + "\n" + heading + "\n\n" + memo_body.rstrip() + "\n"


def apply_merges(
    plans: list[MergePlan], cfg: Config, dry_run: bool = True
) -> ApplyReport:
    """plan_merges() の結果を実適用する。dry_run=True なら read のみ。"""
    report = ApplyReport()

    for plan in plans:
        if not plan.source_exists:
            report.plans_skipped += 1
            continue

        # 1. 統合元の手書きメモを統合先に転記
        try:
            source_text = plan.source_path.read_text(encoding="utf-8")
        except OSError as e:
            report.errors.append(f"統合元読み込み失敗 {plan.source_path}: {e}")
            report.plans_skipped += 1
            continue

        memo_body = _extract_skeleton_body(source_text)

        if plan.target_exists:
            try:
                target_text = plan.target_path.read_text(encoding="utf-8")
            except OSError as e:
                report.errors.append(
                    f"統合先読み込み失敗 {plan.target_path}: {e}"
                )
                report.plans_skipped += 1
                continue
            if memo_body:
                new_target_text = _append_merged_section(
                    target_text, plan.entry.source, memo_body
                )
                if new_target_text != target_text:
                    if not dry_run:
                        plan.target_path.write_text(
                            new_target_text, encoding="utf-8"
                        )
                    report.bodies_merged += 1
        else:
            # 統合先が無い → 単純リネーム(source → target)。
            # ただし body の `# <name>` 見出しもついでに差し替える(skeleton 前提)。
            renamed_text = re.sub(
                rf"^(#\s+){re.escape(plan.entry.source)}\s*$",
                rf"\1{plan.entry.target}",
                source_text,
                count=1,
                flags=re.MULTILINE,
            )
            renamed_text = re.sub(
                rf"^(name:\s+){re.escape(plan.entry.source)}\s*$",
                rf"\1{plan.entry.target}",
                renamed_text,
                count=1,
                flags=re.MULTILINE,
            )
            if not dry_run:
                plan.target_path.parent.mkdir(parents=True, exist_ok=True)
                plan.target_path.write_text(renamed_text, encoding="utf-8")
            report.sources_renamed += 1

        # 2. vault 内 wikilink 一括置換
        for rw in plan.rewrites:
            try:
                text = rw.path.read_text(encoding="utf-8")
            except OSError as e:
                report.errors.append(f"書き換え対象読み込み失敗 {rw.path}: {e}")
                continue
            new_text, count = rewrite_file_text(text, rw.before, rw.after)
            if count == 0:
                continue
            if not dry_run:
                rw.path.write_text(new_text, encoding="utf-8")
            report.files_rewritten += 1
            report.wikilinks_rewritten += count

        # 3. 統合元 skeleton 削除
        if plan.target_exists or plan.source_path != plan.target_path:
            if not dry_run:
                try:
                    plan.source_path.unlink()
                except OSError as e:
                    report.errors.append(
                        f"統合元削除失敗 {plan.source_path}: {e}"
                    )
                    continue
            report.sources_deleted += 1

        report.plans_applied += 1

    return report


# -------------------- ログ整形 --------------------


def format_plan_report(plans: list[MergePlan]) -> str:
    """dry-run / apply 前に表示する人間向けレポート。"""
    lines: list[str] = []
    for plan in plans:
        e = plan.entry
        head = f"[{e.category}] {e.source} → {e.target}"
        if not plan.source_exists:
            lines.append(f"{head}  (skip: 統合元なし)")
            continue
        rw_total = sum(rw.occurrences for rw in plan.rewrites)
        target_state = "存在" if plan.target_exists else "新規"
        skel = "skeleton" if plan.source_is_skeleton else "手書き含む可能性"
        lines.append(
            f"{head}  統合元={skel} / 統合先={target_state} / "
            f"wikilink 書き換え {rw_total} 箇所 ({len(plan.rewrites)} ファイル)"
        )
        for note in plan.notes:
            lines.append(f"    note: {note}")
        for rw in plan.rewrites[:5]:
            try:
                rel = rw.path.relative_to(rw.path.parents[2])
            except (IndexError, ValueError):
                rel = rw.path
            lines.append(f"    - {rel}  ({rw.occurrences} 箇所)")
        if len(plan.rewrites) > 5:
            lines.append(f"    ... 他 {len(plan.rewrites) - 5} ファイル")
    return "\n".join(lines)


def format_apply_report(report: ApplyReport) -> str:
    bits = [
        f"適用 {report.plans_applied} 件 / skip {report.plans_skipped} 件",
        f"  wikilink 書き換え: {report.wikilinks_rewritten} 箇所 "
        f"({report.files_rewritten} ファイル)",
        f"  統合元削除: {report.sources_deleted} 件",
        f"  リネーム (統合先無): {report.sources_renamed} 件",
        f"  メモ転記: {report.bodies_merged} 件",
    ]
    if report.errors:
        bits.append(f"  エラー: {len(report.errors)} 件")
        for err in report.errors[:10]:
            bits.append(f"    - {err}")
    return "\n".join(bits)
