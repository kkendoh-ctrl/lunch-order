"""Phase 2: Claude API で文字起こしを構造化する。

入力: WhisperX が出した transcript dict (segments + text)
出力: claude-structuring.md のスキーマに沿った JSON
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pii
from config import Config, canonical_date_folder


_TRANSCRIPT_PLACEHOLDER = "{{TRANSCRIPT}}"
_SYSTEM_PROMPT_FALLBACK = (
    "あなたは音声記憶アシスタントです。録音の文字起こしを受け取り、"
    "構造化された JSON を返してください。JSON のみ返してください。"
)


def _split_prompt(template: str) -> str:
    """Vault の claude-structuring.md からシステムプロンプトを取り出す。

    `{{TRANSCRIPT}}` を区切り文字として、その前までを system に使う。
    Markdown の ```...``` フェンスがあれば除去。"""
    if _TRANSCRIPT_PLACEHOLDER in template:
        system_part = template.split(_TRANSCRIPT_PLACEHOLDER, 1)[0]
    else:
        system_part = template
    # 最初の ``` 以前を捨て、最後の ``` 以降も捨てる(フェンスの中身だけ取る)
    fences = re.findall(r"```[a-z]*\n(.*?)```", system_part, flags=re.DOTALL)
    if fences:
        # 最大の本文をシステムプロンプトとする
        return max(fences, key=len).strip()
    return system_part.strip()


def _format_transcript_for_user(transcript: dict) -> str:
    """WhisperX の出力をプロンプトに渡しやすい形にする。
    タイムスタンプ付きの一行ずつ + メタ情報を上に。"""
    date = transcript.get("date", "")
    time = transcript.get("time", "")
    duration = transcript.get("duration_s", 0)
    lines = [
        f"録音日時: {date} {time}",
        f"長さ: {duration:.1f} 秒",
        "",
        "本文(タイムスタンプ付き):",
    ]
    for seg in transcript.get("segments", []):
        start = seg.get("start", 0)
        text = seg.get("text", "").strip()
        if not text:
            continue
        mm = int(start // 60)
        ss = int(start % 60)
        lines.append(f"[{mm:02d}:{ss:02d}] {text}")
    return "\n".join(lines)


def _enrich_transcript_meta(transcript: dict, audio_path: Path) -> dict:
    """transcript に date/time(audio ファイル名・ディレクトリ名由来)を補う。
    既に入っていればそれを優先。

    date は canonical_date_folder() で決める(parent が非 canonical でも
    metadata/mtime で日付を推定する)。"""
    if "date" not in transcript or "time" not in transcript:
        date = canonical_date_folder(audio_path)
        # ファイル名: HH-MM-SS → HH:MM:SS
        stem = audio_path.stem
        if re.fullmatch(r"\d{2}-\d{2}-\d{2}", stem):
            time = stem.replace("-", ":")
        else:
            time = stem
        return {**transcript, "date": transcript.get("date", date), "time": transcript.get("time", time)}
    return transcript


def _extract_json(text: str) -> dict:
    """Claude のレスポンスから JSON を取り出す。
    ```json ... ``` フェンスや前置きが付いていても拾う。

    JSON が一切取れない場合は ValueError。呼び出し側で
    `_markdown_to_fallback_structured` にフォールバックする運用。"""
    text = text.strip()
    # まず素直にパースを試す
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # ```...``` フェンスから抜き出す
    fences = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    for f in fences:
        try:
            return json.loads(f.strip())
        except json.JSONDecodeError:
            continue
    # 最初の { から最後の } までを抜き出す
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Claude の応答から JSON を抽出できませんでした: {text[:200]}...")


def _markdown_to_fallback_structured(text: str) -> dict:
    """JSON 抽出失敗時のセーフネット。Markdown 応答を1つの context に詰める。

    低品質な文字起こしを見た Claude が「これは構造化に値しない」と判断して
    人間向けの Markdown レポートを返した場合などに使う。録音内容を完全に
    失うよりは、生の Markdown を summary に格納して importance=2 の context
    を 1 つ作り、ノート生成を続行する。`domains=["要レビュー"]` を付けて
    あとから一覧でフィルタできるようにする。"""
    cleaned = text.strip()
    # H1 タイトル抽出(無ければ汎用タイトル)
    title_m = re.match(r"^#\s+(.+?)\s*$", cleaned, flags=re.MULTILINE)
    title = title_m.group(1).strip() if title_m else "構造化失敗(Markdown フォールバック)"
    # 長すぎる場合は summary を切り詰める(Obsidian 上の見やすさ優先)
    body = cleaned
    if len(body) > 4000:
        body = body[:4000] + "\n\n...(以下省略、原文は transcript JSON 参照)"
    return {
        "contexts": [
            {
                "title": title,
                "importance": 2,
                "sentiment": "ニュートラル",
                "domains": ["要レビュー"],
                "summary": (
                    "⚠️ Claude が JSON 形式で構造化を返さなかったため、"
                    "Markdown 応答をそのまま格納しています。手動レビュー推奨。\n\n"
                    f"{body}"
                ),
                "key_points": [],
                "open_questions": [
                    "構造化失敗の原因は録音品質か Claude の挙動か(transcript を確認)",
                ],
                "counterpart": [],
                "topics": [],
                "locations": [],
                "todos": [],
            }
        ],
    }


def structure_transcript(
    transcript: dict, audio_path: Path, cfg: Config
) -> dict:
    """transcript → Claude → 構造化 JSON。
    呼び出し前に cfg.structuring_enabled を確認すること。"""
    if not cfg.structuring_enabled:
        raise RuntimeError(
            "ANTHROPIC_API_KEY が未設定。.env で設定するか structuring_enabled で分岐してください"
        )

    import anthropic  # 重い import は関数内で

    template = cfg.load_structuring_prompt()
    if not template:
        system_prompt = _SYSTEM_PROMPT_FALLBACK
    else:
        system_prompt = _split_prompt(template)

    transcript = _enrich_transcript_meta(transcript, audio_path)

    # Phase 4: Claude に送る直前にマスキング。vault に書く transcript は元のまま。
    masker = pii.PIIMasker.from_config(cfg)
    masked_transcript, mask_count = pii.mask_transcript(transcript, masker)
    user_content = _format_transcript_for_user(masked_transcript)

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    response = client.messages.create(
        model=cfg.anthropic_model,
        max_tokens=cfg.anthropic_max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": cfg.anthropic_effort},
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    text_parts = [b.text for b in response.content if b.type == "text"]
    if not text_parts:
        raise RuntimeError(
            f"Claude が text ブロックを返さなかった: stop_reason={response.stop_reason}"
        )
    raw = "\n".join(text_parts)
    try:
        structured = _extract_json(raw)
        structuring_format = "json"
    except ValueError:
        # JSON 抽出失敗。Markdown レスポンスを 1 つの context にまとめて続行。
        # 例外を投げて Phase 2 全体を落とすより、低品質結果でも note を作って
        # 人間にレビューさせる方が運用上ロスが少ない。
        structured = _markdown_to_fallback_structured(raw)
        structuring_format = "markdown_fallback"

    return {
        "structured": structured,
        "structuring_format": structuring_format,
        "model": response.model,
        "structured_at": datetime.now(timezone.utc).isoformat(),
        "pii_masked": mask_count,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_creation_input_tokens": getattr(
                response.usage, "cache_creation_input_tokens", 0
            ),
            "cache_read_input_tokens": getattr(
                response.usage, "cache_read_input_tokens", 0
            ),
        },
    }
