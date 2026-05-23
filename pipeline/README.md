# Phase 1+2: WhisperX 文字起こし + Claude 構造化パイプライン

`iCloud Drive/Just Press Record/` を監視し、新規 `.m4a` を:

1. **Phase 1** WhisperX で文字起こし → `音声記憶/_transcripts/YYYY-MM-DD/HH-MM-SS.json`
2. **Phase 2** Claude API で構造化 → `音声記憶/録音/YYYY-MM-DD/HH-MM-SS.md`

Phase 2 は `ANTHROPIC_API_KEY` が設定されていれば自動で連鎖実行。未設定なら Phase 1 だけで止まる。

## ThinkPad セットアップ(WSL2 Ubuntu 前提)

### 1. システム依存

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv ffmpeg
```

### 2. プロジェクト clone

```bash
cd ~
git clone https://github.com/kkendoh-ctrl/lunch-order.git
cd lunch-order/pipeline
```

### 3. Python 仮想環境

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 4. PyTorch (CPU 版)

WhisperX は torch を要求するが、デフォルトでは CUDA 版を引いて来て巨大になる。Intel Arc は CUDA 非対応なので CPU 版を先に入れる。

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### 5. その他の依存

```bash
pip install -r requirements.txt
```

WhisperX 初回実行時に large-v3 モデル(~3GB)が `~/.cache/huggingface/` にダウンロードされる。

### 6. `.env` を作る

```bash
cp .env.example .env
```

`.env` を編集。Windows ユーザー名 `<user>` を自分のに置き換える(`echo $USER` ではなく Windows 側のユーザー名):

```
JPR_INBOX_PATH=/mnt/c/Users/<user>/iCloud Drive/Just Press Record
VAULT_PATH=/mnt/c/Users/<user>/iCloud Drive/音声記憶
ANTHROPIC_API_KEY=sk-ant-...   # Phase 2 を動かすなら設定
```

iCloud のフォルダ名はロケールによっては `iCloudDrive` (空白なし) になっていることもあるので、`ls /mnt/c/Users/<user>/` で実際に存在するパスを確認。

`ANTHROPIC_API_KEY` 未設定なら Phase 1 (文字起こし) だけ動く。後から API キーを設定して `python main.py batch` を再実行すれば、既存の `_transcripts/*.json` から Phase 2 だけ追加で走らせられる。

### 7. 動作確認

```bash
# 設定値が正しく読めるか確認
python main.py info

# 1ファイルだけ試しに文字起こし(WhisperX 起動の動作確認)
python main.py test "/mnt/c/Users/<user>/iCloud Drive/Just Press Record/2026-05-23/13-39-19.m4a"
```

## 運用コマンド

| コマンド | 説明 |
|---|---|
| `python main.py info` | 設定値と環境を表示。動作前のヘルスチェック |
| `python main.py test <audio>` | 単一ファイルを処理(軽フィルタ + 文字起こし + 構造化) |
| `python main.py batch` | 未処理ファイルを全部処理して終了 |
| `python main.py watch` | watchdog で常駐、新規ファイルを順次処理 |
| `python main.py structure <transcript.json>` | 既存 transcript JSON から Phase 2 だけ単体実行(デバッグ用) |

## 出力

```
音声記憶/
├── _transcripts/                  ← Phase 1 の出力
│   └── 2026-05-23/
│       ├── 13-39-19.json          ← WhisperX 出力(セグメント+タイムスタンプ)
│       ├── 13-40-02.skipped       ← 軽フィルタで除外したマーカー(再処理されない)
│       └── ...
└── 録音/                          ← Phase 2 の出力
    └── 2026-05-23/
        └── 13-39-19.md            ← Claude 構造化済みノート(YAML フロントマター + 本文)
```

`.json` の中身:

```json
{
  "audio_path": ".../Just Press Record/2026-05-23/13-39-19.m4a",
  "duration_s": 14.2,
  "model": "large-v3",
  "language": "ja",
  "transcribed_at": "2026-05-23T13:40:00Z",
  "segments": [
    {"start": 0.0, "end": 2.5, "text": "こんにちは、田中です"},
    {"start": 2.5, "end": 5.1, "text": "..."}
  ],
  "text": "全文連結したもの"
}
```

`.skipped` の中身:

```json
{
  "reason": "too_short",
  "duration_s": 3.1,
  "skipped_at": "2026-05-23T13:40:00Z"
}
```

## トラブルシュート

### `/mnt/c/Users/.../iCloud Drive/` が見つからない

- iCloud for Windows でちゃんと「iCloud Drive を File Explorer に同期」が ON になってるか確認
- WSL2 で `ls "/mnt/c/Users/$(whoami)/"` してフォルダ名を実機で確認
- ロケールによっては `iCloudDrive` (空白なし) のことも

### 「ファイルがダウンロードされてない」エラー

- iCloud のクラウドアイコン付きファイルは実体が無いので読めない
- エクスプローラで該当フォルダを右クリック → 「常にこのデバイスに保持」

### WhisperX の初回ロードが遅い / メモリ不足

- 初回は ~3GB のモデルダウンロードが走る。気長に待つ
- メモリ8GB 切る場合は `WHISPER_MODEL=medium` か `small` に落とす

### `ffmpeg not found`

- `which ffmpeg` で確認。なければ `sudo apt install ffmpeg`

## Phase 2 の中身

- モデル: `claude-opus-4-7`(`.env` の `ANTHROPIC_MODEL` で変更可)
- Adaptive thinking + effort `medium`(`ANTHROPIC_EFFORT` で調整)
- システムプロンプトは Vault の `_プロンプト/claude-structuring.md` を読む
  - 大きいので **prompt caching** を有効化(2回目以降は ~90% 安い)
  - プロンプトを編集すると一度キャッシュが無効化される
- 1録音から複数コンテキストの抽出に対応(電話中に話題が転換した場合など)
- Claude が「雑談・テスト録音」と判断したら `contexts: []` が返り、ノートは空セクションで生成される

## 次のフェーズ

- Phase 3: エンティティ抽出と自動リンク(`[[人物]]` `[[トピック]]` ノートを skeleton 生成 + 日次ノート集約)
- Phase 4: PII マスキング(Claude 送信前に電話番号・申請番号等を伏字化)
- Phase 5: 話者分離など

詳細は `docs/voice-pipeline.md` 参照。
