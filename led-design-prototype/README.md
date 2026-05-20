# LED化工事設計書ジェネレータ (プロトタイプ v0.1)

浦安市のスポーツ施設（野球場・テニスコート・競技場）におけるLED化工事の設計書ドラフトを、AIで自動生成する最小プロトタイプ。

## できること

- 施設情報・既存灯具データ（YAML）から設計書ドラフトを生成
- JIS Z 9127（スポーツ照明基準）に基づく必要照度の試算
- 灯具数・消費電力・省エネ効果の概算
- Markdownで設計書本文を出力（後でWord変換可能）

## できないこと（人が確認すべき）

- 現地調査・支柱の構造再計算
- 電気主任技術者の確認・押印
- 浦安市固有の積算様式への完全準拠（雛形のみ）
- 図面作成（CAD）

## セットアップ

```bash
cd led-design-prototype
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Claude APIキーを設定
export ANTHROPIC_API_KEY="sk-ant-..."
```

## 使い方

```bash
# サンプル（野球場）で生成
python -m src.generate inputs/sample_baseball.yaml

# 出力先
ls outputs/
```

## ディレクトリ構成

```
led-design-prototype/
├── inputs/         # 案件入力（YAML）
├── knowledge/      # RAG用の参照資料（JIS、特記仕様、カタログ）
├── templates/      # 設計書テンプレート
├── src/            # 生成スクリプト
│   ├── generate.py    # メインエントリ
│   ├── illuminance.py # 照度計算
│   └── output.py      # Markdown出力
└── outputs/        # 生成結果
```

## 入力YAMLのフォーマット

`inputs/sample_baseball.yaml` を参照。

## 注意事項

- 出力はあくまで**ドラフト**。実際の発注前に有資格者の確認が必須
- 単価・労務費は公開情報ベースのため、実際の積算は浦安市単価を反映すること
- JIS照度基準は要約版を投入しているため、正確な値は規格本書で要確認
