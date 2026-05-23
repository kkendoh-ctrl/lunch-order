# Phase 1: WhisperX 文字起こしパイプライン

`iCloud Drive/Just Press Record/` を監視し、新規 `.m4a` を WhisperX で文字起こしして `音声記憶/_transcripts/YYYY-MM-DD/HH-MM-SS.json` に出力する。

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
```

iCloud のフォルダ名はロケールによっては `iCloudDrive` (空白なし) になっていることもあるので、`ls /mnt/c/Users/<user>/` で実際に存在するパスを確認。

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
| `python main.py test <audio>` | 単一ファイルを処理(軽フィルタ + 文字起こし) |
| `python main.py batch` | 未処理ファイルを全部処理して終了 |
| `python main.py watch` | watchdog で常駐、新規ファイルを順次処理 |

## 出力

```
音声記憶/_transcripts/
└── 2026-05-23/
    ├── 13-39-19.json        ← WhisperX 出力(セグメント+タイムスタンプ)
    ├── 13-40-02.skipped     ← 軽フィルタで除外したマーカー(再処理されない)
    └── ...
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

## 次のフェーズ

- Phase 2 (`pipeline/p2_structure.py`): Claude API で構造化、Vault の `録音/` にノート生成
- Phase 3: エンティティ抽出と自動リンク
- Phase 4: PII マスキング
- Phase 5: 話者分離など

詳細は `docs/voice-pipeline.md` 参照。
