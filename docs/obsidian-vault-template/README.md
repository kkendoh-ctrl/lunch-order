# Obsidian Vault テンプレート: 音声記憶

このフォルダの中身を **そのまま** `iCloud Drive/音声記憶/` にコピーしてください。Obsidian で開けば、`録音/` `日次/` `人物/` `トピック/` `場所/` `一覧/` `_テンプレート/` `_プロンプト/` のフォルダ構造とテンプレ・プロンプトが揃った状態で使い始められます。

## 含まれているもの

- `録音/` `日次/` `人物/` `トピック/` `場所/` `一覧/` `_生成ログ/` — 空フォルダ(`.gitkeep` で管理)
- `一覧/ToDo.md` — 全 ToDo の集約先(初期はプレースホルダ、パイプラインが上書き)
- `一覧/重要度高.md` — 重要度4-5の録音一覧(同上)
- `_テンプレート/` — 手動でノートを作るときの雛形
  - `録音ノート.md`
  - `日次ノート.md`
  - `人物ノート.md`
  - `トピックノート.md`
- `_プロンプト/` — ThinkPad パイプラインが参照する LLM プロンプト
  - `claude-structuring.md` — Claude API への構造化指示プロンプト
  - `whisper-initial-prompt.txt` — WhisperX の `initial_prompt`(業務用語+私的用語)

## コピー方法

### 方法1: GitHub からダウンロード

1. このリポジトリの `docs/obsidian-vault-template/` をブラウザで開く
2. 各ファイル/フォルダを `iCloud Drive/音声記憶/` にコピー

### 方法2: clone してコピー

```bash
git clone https://github.com/kkendoh-ctrl/lunch-order.git
cp -r lunch-order/docs/obsidian-vault-template/* "/path/to/iCloud Drive/音声記憶/"
```

### 方法3: ThinkPad のエクスプローラから

1. このリポジトリの ZIP をダウンロードして展開
2. `docs/obsidian-vault-template/` の中身を選択 → コピー
3. `iCloud Drive/音声記憶/` に貼り付け

## コピー後

1. Obsidian で `音声記憶` を Vault として開く(`Open folder as vault`)
2. サイドバーに上記フォルダが見えれば OK
3. `_テンプレート/` の中身を編集して自分の好みに合わせる(任意)
4. `_プロンプト/whisper-initial-prompt.txt` に固有名詞・業務用語・家族の名前などを追記(精度に効く)

## このフォルダ自体は Vault に含めない

`README.md`(このファイル)は Vault に入れる必要はありません。コピーするのは `README.md` 以外の中身です。
