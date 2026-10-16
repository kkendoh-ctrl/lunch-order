# Phase 6 検討: GiNZA NER による未登録人名の自動マスク

最終更新: 2026-05-23

Phase 4 PII マスキング実装時に「仕様 §4.3.5 で言及されていた GiNZA/spaCy
NER は依存重・spec で『オプション』のため Phase 5+ に繰越」と判断した件の
継続検討メモ。

## 仕様での要請(§4.3.5 再掲)

> spaCy/GiNZA で人名・組織名を検出して伏字化(オプション):
> - 業務文脈では「課長」「○○課」など固有名詞も意味を持つので、伏字化しすぎると要約品質が落ちる
> - 推奨: 個人名のうち「マスク辞書に明示登録されたもの以外」を伏字化、組織・役職は残す
> - **許可リスト方式**: 浦安市・市民スポーツ課・既知関係先・家族はマスクしない
> - 自分(遠藤)の発言は伏字化しない

## 仮に実装した場合のコスト

| 項目 | 数値・状況 |
|---|---|
| 追加依存 | `spacy>=3.7` + `ja_ginza>=5.1` |
| インストールサイズ | spacy 本体 ~120MB + ja_ginza モデル ~200MB |
| Python 互換性 | spacy 3.7 は Python 3.9〜3.12。**bronzeman の 3.11 で OK** |
| 起動オーバーヘッド | 初回 `spacy.load("ja_ginza")` で 2〜5 秒 |
| 推論コスト | 1セグメント (~10 秒音声相当の文字列) で ~50〜200ms |
| 推論モデルキャッシュ | プロセス内 1 回ロード、以降は in-memory |

bronzeman のストレージ残量が厳しいので、**追加 200MB のモデルを置く価値が
ある運用なら入れる**判断。

## NER の精度問題

GiNZA の `PERSON` ラベルは、実運用では:
- **False negative**: 「田中課長」を 1 つのトークンとして組織関連扱いして
  `PERSON` を逃すケースが多い
- **False positive**: 一般名詞や略語を人名と誤判定する
- **語尾**: 「さん」「氏」は別トークン扱い → 「田中」だけマスクして「さん」が
  残る不格好な出力になりがち

要するに「機械的に拾える率は 7 割程度」と考えるべきで、過信は禁物。

## 既存パイプラインの代替アプローチ

PII マスキングの目的は **「クラウドに送らない」** ことなので、NER で全自動
取り切るより、運用しながら `pii_dict.yaml` を育てる方が現実的・堅牢。

### 提案: NER は使わず、`pii suggest` コマンドを追加

NER をオンラインのマスキングパスから外し、**オフラインの辞書育成支援**に
回す案。

```bash
# 既存の transcript JSON を全部スキャン、PII 候補をリストアップ
python main.py pii suggest

# 出力例:
# === 未登録の人名候補(出現回数順) ===
# 田中  43 件  [録音/2026-05-23/13-39-19, 2026-05-22/10-30-00, ...]
# 山田  12 件  [...]
# 鈴木   8 件  [...]
#
# === 未登録の組織候補 ===
# (株)○○工務店  3 件  [...]
#
# 追加するなら pii_dict.yaml に:
#   田中: "[個人A]"
#   山田: "[個人B]"
# 等を書く。
```

設計のキモ:
- NER は **transcript JSON にだけ走らせる**(録音1本ずつではなく、まとめて
  バッチ処理)
- 結果は `pii_dict.yaml` への提案として表示するだけ。**書き込みはしない**
  (ユーザーが取捨選択)
- 既存マスク済みトークン (`[個人A]` 等)・許可リスト (`pii_allowlist.yaml`)
  に載っている語は除外
- 出現回数閾値で雑音カット(2 回未満は表示しない、等)

### この案の利点

1. **オンライン経路はゼロコスト**: `python main.py test` の処理時間が増えない
2. **誤検出の影響が無い**: NER が間違えても提案を採用しなければよい
3. **既存テストへの影響ゼロ**: 別コマンドなので疎結合
4. **ユーザー主導**: 辞書は手動で育つ → 透明性が高い

### この案の欠点

- 「今日録音した内容に未登録の人名が出てきたらリアルタイムにマスクして
  Claude に送らない」という強い要件には応えられない
  - ただし bronzeman ローカル運用前提で、Claude API は「学習に使わない / 短期
    保持」が約束されている (§2.1) ので、現実的にはリスク低

## 結論

**Phase 6 として `pii suggest` (NER 辞書育成支援コマンド) を実装する案を
推奨**。オンラインマスクパスへの NER 組込みはしない方針で固定。

## 実装プラン(将来やる時の参考)

```python
# pipeline/pii_suggest.py
import spacy

def suggest_from_transcripts(cfg: Config, min_occurrences: int = 2) -> dict:
    """Vault の _transcripts/ を全部読み、PII 候補を返す。"""
    nlp = spacy.load("ja_ginza")
    # 既存の dict / allowlist を読む
    existing_dict_keys = _load_pii_dict_keys(cfg)
    allowlist = _load_pii_allowlist(cfg)
    
    counts: dict[str, dict[str, int]] = {
        "PERSON": defaultdict(int),
        "ORG": defaultdict(int),
        "GPE": defaultdict(int),
    }
    
    for json_path in cfg.transcripts_dir.rglob("*.json"):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        text = data.get("text", "")
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ not in counts:
                continue
            name = ent.text.strip()
            if name in existing_dict_keys or name in allowlist:
                continue
            counts[ent.label_][name] += 1
    
    # min_occurrences 以上だけ返す
    return {
        label: {k: v for k, v in items.items() if v >= min_occurrences}
        for label, items in counts.items()
    }
```

CLI 側:

```python
@cli.group()
def pii():
    """PII マスキング辞書の管理。"""

@pii.command("suggest")
@click.option("--min", "min_occurrences", default=2, help="最低出現回数")
def pii_suggest(min_occurrences: int) -> None:
    cfg = Config.load()
    out = pii_suggest_module.suggest_from_transcripts(cfg, min_occurrences)
    # 表示...
```

依存追加(発動時のみ):
```
# requirements-pii-suggest.txt (optional, インストールは別)
spacy>=3.7,<3.8
ja-ginza>=5.1
```

## 関連: 自分(遠藤)の発言を伏字化しない要件

GiNZA でも分からない情報なので、これは仕様 §4.3.5 の話だが現実的には対処不能:
- 単一話者録音(独り言)では話者識別不要
- 複数話者なら Phase 5c の diarization で `speaker` ラベルが付くので、
  そこから「SPEAKER_00 が自分」を CLI / 設定で明示するアプローチ
- これは Phase 5c が実機で動いてから検討
