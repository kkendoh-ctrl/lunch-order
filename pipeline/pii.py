"""Phase 4: PII マスキング層。

Claude API に送る前に文字起こしから電話番号・メール・郵便番号・
クレジットカード番号などをマスクする。+ ユーザー辞書(`pii_dict.yaml`)
による任意置換。

設計方針:
- マスクは「クラウド (Claude API) に送らない」目的のためだけに行う。
- vault の `## 全文(タイムスタンプ付き)` には **マスク前の生テキスト** が残る。
  vault は ThinkPad ローカルにあり OS 側で暗号化される前提(spec §2.1)。
- Claude の structured 出力(summary / counterpart / todos など)はマスク済み
  文字列を入力にしているので、当然マスク済みのまま vault に書かれる。

GiNZA/spaCy による NER ベースの人名検出は仕様上「オプション」なので
Phase 4 では実装しない(依存が重い)。Phase 5 以降で検討。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from config import Config


# 日本語混在テキストでは `\b` (word boundary) が機能しない(`\w` は日本語も
# 単語文字扱いなので「は080-」のような並びでは境界が立たない)。
# 数字の前後だけ「数字でない」ことをチェックする lookbehind/lookahead を使う。
_BUILTIN_RULES: list[tuple[re.Pattern, str]] = [
    # メール(@ を含むので比較的誤爆しにくい)
    (re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+"), "[メール]"),
    # クレジットカード様: 16 桁 (4-4-4-4 をハイフン or 空白 or 詰めて)
    (
        re.compile(r"(?<!\d)\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}(?!\d)"),
        "[カード番号]",
    ),
    # 日本の電話番号: 0XX-XXXX-XXXX / 0X-XXXX-XXXX 等
    (re.compile(r"(?<!\d)0\d{1,4}-\d{1,4}-\d{4}(?!\d)"), "[電話番号]"),
    # 郵便番号: XXX-XXXX(3+4 桁ハイフン区切り)
    (re.compile(r"(?<!\d)\d{3}-\d{4}(?!\d)"), "[郵便番号]"),
    # 申請番号など 7 桁単独。郵便番号より後に当てる(郵便番号は既に置換済み)。
    # 誤爆しやすい(電話の末尾4桁 + 3桁 など)が、上のハイフン付きパターンが
    # 先に当たれば守られる。
    (re.compile(r"(?<!\d)\d{7}(?!\d)"), "[申請番号]"),
]


@dataclass
class MaskResult:
    text: str
    replacements: int  # 置換が走った回数(マッチ数の合計)


class PIIMasker:
    """正規表現ルール + ユーザー辞書(substring 置換)による単純な PII マスカ。

    - `dict_rules`: substring 一致で置換。長いキーから先に処理して、
      短いキーが先に当たって長いキーの一部を壊すのを防ぐ。
    - `enabled=False` なら mask() はノーオペ。"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        dict_rules: dict[str, str] | None = None,
        regex_rules: list[tuple[re.Pattern, str]] | None = None,
    ) -> None:
        self.enabled = enabled
        self.dict_rules = dict(dict_rules or {})
        self.regex_rules = (
            list(regex_rules) if regex_rules is not None else list(_BUILTIN_RULES)
        )
        # 辞書キーは長い順
        self._sorted_dict_keys = sorted(
            (k for k in self.dict_rules if k), key=len, reverse=True
        )

    def mask(self, text: str) -> MaskResult:
        if not self.enabled or not text:
            return MaskResult(text=text or "", replacements=0)
        n = 0
        # 1) ユーザー辞書(長い順)
        for k in self._sorted_dict_keys:
            count = text.count(k)
            if count:
                text = text.replace(k, self.dict_rules[k])
                n += count
        # 2) 正規表現
        for pattern, repl in self.regex_rules:
            text, sub_n = pattern.subn(repl, text)
            n += sub_n
        return MaskResult(text=text, replacements=n)

    @classmethod
    def from_config(cls, cfg: "Config") -> "PIIMasker":
        """Config から生成。`pii_mask_enabled=False` ならノーオペ masker。"""
        if not cfg.pii_mask_enabled:
            return cls(enabled=False)
        dict_rules = _load_dict(cfg.pii_dict_path)
        return cls(enabled=True, dict_rules=dict_rules)


def _load_dict(path: Path | None) -> dict[str, str]:
    """`pii_dict.yaml` を読む。

    形式は flat dict (キー: 置換先):
    ```yaml
    田中花子: "[個人A]"
    090-1234-5678: "[電話番号]"
    ```

    - パスが None / ファイル無し / 中身が空なら {} を返す
    - 値が null のキーは `[マスク]` で置換
    - dict 以外が入っていれば ValueError"""
    if not path or not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(
            f"pii_dict.yaml は flat dict である必要があります: 実際 = {type(raw).__name__}"
        )
    out: dict[str, str] = {}
    for k, v in raw.items():
        if k is None or k == "":
            continue
        out[str(k)] = str(v) if v is not None else "[マスク]"
    return out


def mask_transcript(transcript: dict, masker: PIIMasker) -> tuple[dict, int]:
    """transcript の `segments[].text` と `text` 全てにマスクをかける。

    元の dict は変更せず、必要なフィールドだけ差し替えた新しい dict を返す。
    返り値: (新 transcript, 総置換件数)"""
    if not masker.enabled:
        return transcript, 0
    new = dict(transcript)
    total = 0
    segments = transcript.get("segments")
    if segments:
        new_segments = []
        for seg in segments:
            new_seg = dict(seg)
            if seg.get("text"):
                r = masker.mask(seg["text"])
                new_seg["text"] = r.text
                total += r.replacements
            new_segments.append(new_seg)
        new["segments"] = new_segments
    if transcript.get("text"):
        r = masker.mask(transcript["text"])
        new["text"] = r.text
        total += r.replacements
    return new, total
