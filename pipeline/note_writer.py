"""Phase 2: 構造化 JSON → Obsidian Markdown ノート生成。

1録音 = 1ノート(`録音/YYYY-MM-DD/HH-MM-SS.md`)。
人物/トピック/場所への自動リンク生成(skeleton 作成)は Phase 3。
ここでは録音ノートの中に `[[]]` リンク表記だけ出力する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from config import Config


_AUDIO_REL_PARTS = 2  # 録音/YYYY-MM-DD/foo.md からの「..」の数


def _wikilink(name: str) -> str:
    """`田中さん` → `[[田中さん]]`。既に [[ で始まっているならそのまま。"""
    name = name.strip()
    if not name:
        return ""
    if name.startswith("[[") and name.endswith("]]"):
        return name
    return f"[[{name}]]"


def _format_seconds(s: float) -> str:
    s = int(round(s))
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    return f"{m}m{sec:02d}s"


def _normalize_time(value: str | None) -> str:
    """HH:MM:SS / HH-MM-SS / HHMM などを HH:MM:SS に寄せる(失敗時はそのまま)。"""
    if not value:
        return ""
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}", value):
        return value
    if re.fullmatch(r"\d{2}-\d{2}-\d{2}", value):
        return value.replace("-", ":")
    return value


def _audio_rel_path(audio_path: Path, vault: Path) -> str:
    """ノートから見た音声ファイルへの相対パス。
    Vault が /mnt/c/Users/.../iCloud Drive/音声記憶/ で
    audio が /mnt/c/Users/.../iCloud Drive/Just Press Record/2026-05-23/13-39-19.m4a なら
    ../../Just Press Record/2026-05-23/13-39-19.m4a を返す。"""
    try:
        return str(Path("../..") / audio_path.relative_to(vault.parent))
    except ValueError:
        # vault.parent 配下に audio が無い場合は絶対パスでフォールバック
        return str(audio_path)


def _format_frontmatter(meta: dict) -> str:
    """YAML フロントマター。ensure_ascii=False 相当(allow_unicode)。"""
    return yaml.safe_dump(
        meta, allow_unicode=True, sort_keys=False, default_flow_style=False
    )


def _collect_unique(contexts: list[dict], key: str) -> list[str]:
    seen: dict[str, None] = {}
    for c in contexts:
        for item in c.get(key, []) or []:
            if not item:
                continue
            text = str(item).strip()
            if text and text not in seen:
                seen[text] = None
    return list(seen.keys())


def _max_importance(contexts: list[dict]) -> int:
    best = 0
    for c in contexts:
        try:
            v = int(c.get("importance") or 0)
        except (TypeError, ValueError):
            v = 0
        if v > best:
            best = v
    return best


def _domain_tags(contexts: list[dict]) -> list[str]:
    seen: dict[str, None] = {}
    for c in contexts:
        for d in c.get("domains", []) or []:
            if d:
                seen[str(d)] = None
    return list(seen.keys())


def render_note(
    transcript: dict,
    result: dict,
    audio_path: Path,
    cfg: Config,
) -> str:
    """構造化結果 + transcript → Markdown 全文。"""
    structured = result.get("structured", {}) or {}
    contexts: list[dict] = structured.get("contexts") or []

    date = structured.get("date") or transcript.get("date", "")
    time = _normalize_time(structured.get("time") or transcript.get("time", ""))
    duration_s = float(
        structured.get("duration_s") or transcript.get("duration_s") or 0
    )

    counterparts = _collect_unique(contexts, "counterpart")
    topics = _collect_unique(contexts, "topics")
    locations = _collect_unique(contexts, "locations")
    domains = _domain_tags(contexts)
    importance = _max_importance(contexts)
    # sentiment は各 context で単一の文字列。最大重要度の context のものを採用
    sentiment = "ニュートラル"
    if contexts:
        top = max(contexts, key=lambda c: int(c.get("importance") or 0))
        sentiment = (top.get("sentiment") or "ニュートラル").strip() or "ニュートラル"

    tags = ["録音"] + list(domains)
    if importance >= 4:
        tags.append("重要")

    fm = {
        "date": date,
        "time": time,
        "duration": _format_seconds(duration_s),
        "audio_path": _audio_rel_path(audio_path, cfg.vault),
        "counterpart": [_wikilink(n) for n in counterparts],
        "topics": [_wikilink(t) for t in topics],
        "locations": [_wikilink(l) for l in locations],
        "domains": domains,
        "importance": importance or 3,
        "sentiment": sentiment,
        "tags": tags,
        "model": result.get("model", ""),
        "structured_at": result.get("structured_at", ""),
    }

    lines: list[str] = []
    lines.append("---")
    lines.append(_format_frontmatter(fm).rstrip())
    lines.append("---")
    lines.append("")

    title_short = time[:5] if len(time) >= 5 else time
    title_extra = ""
    if contexts and contexts[0].get("title"):
        title_extra = " " + contexts[0]["title"]
    lines.append(f"# {title_short}{title_extra}".rstrip())
    lines.append("")

    if not contexts:
        lines.append("> Claude が「雑談・テスト録音」と判断し、構造化を出力しませんでした。")
        lines.append("")
    else:
        for i, c in enumerate(contexts, 1):
            heading_parts: list[str] = []
            ctx_title = c.get("title") or f"コンテキスト{i}"
            heading_parts.append(ctx_title)
            start_time = c.get("start_time") or ""
            end_time = c.get("end_time") or ""
            if start_time or end_time:
                heading_parts.append(f"({start_time}–{end_time})")
            lines.append(f"## {' '.join(heading_parts)}")
            lines.append("")

            # メタ行
            meta_bits = []
            if c.get("importance"):
                meta_bits.append(f"重要度: {c['importance']}")
            if c.get("sentiment"):
                meta_bits.append(f"感情: {c['sentiment']}")
            doms = c.get("domains") or []
            if doms:
                meta_bits.append("領域: " + ", ".join(doms))
            if meta_bits:
                lines.append(" / ".join(meta_bits))
                lines.append("")

            if c.get("summary"):
                lines.append("### 要約")
                lines.append(c["summary"].strip())
                lines.append("")

            todos = c.get("todos") or []
            if todos:
                lines.append("### ToDo")
                for t in todos:
                    text = (t.get("text") or "").strip()
                    if not text:
                        continue
                    bits = [text]
                    if t.get("due"):
                        bits.append(f"(期限: {t['due']})")
                    if t.get("assignee") and t["assignee"] not in ("self", "自分"):
                        bits.append(f"@{t['assignee']}")
                    lines.append(f"- [ ] {' '.join(bits)} #todo")
                lines.append("")

            key_points = c.get("key_points") or []
            if key_points:
                lines.append("### キーポイント")
                for kp in key_points:
                    lines.append(f"- {kp}")
                lines.append("")

            open_qs = c.get("open_questions") or []
            if open_qs:
                lines.append("### 未解決の論点")
                for q in open_qs:
                    lines.append(f"- {q}")
                lines.append("")

            ctx_links = []
            for n in c.get("counterpart") or []:
                if n:
                    ctx_links.append(_wikilink(n))
            for t in c.get("topics") or []:
                if t:
                    ctx_links.append(_wikilink(t))
            for l in c.get("locations") or []:
                if l:
                    ctx_links.append(_wikilink(l))
            if ctx_links:
                lines.append("### 関連")
                for link in ctx_links:
                    lines.append(f"- {link}")
                lines.append("")

    # 全文(タイムスタンプ付き)
    lines.append("## 全文(タイムスタンプ付き)")
    lines.append("")
    for seg in transcript.get("segments", []):
        start = seg.get("start", 0)
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        mm = int(start // 60)
        ss = int(start % 60)
        speaker = seg.get("speaker")
        speaker_tag = f" {{{speaker}}}" if speaker else ""
        lines.append(f"[{mm:02d}:{ss:02d}]{speaker_tag} {text}")
    lines.append("")

    # 日次ノートへの参照
    if date:
        lines.append("## 関連")
        lines.append(f"- [[{date}]]")
        lines.append("")

    # 音声本体への相対リンク
    audio_url = _audio_rel_path(audio_path, cfg.vault).replace(" ", "%20")
    lines.append("---")
    lines.append(f"[原音を再生]({audio_url})")

    return "\n".join(lines) + "\n"


def save_note(content: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
