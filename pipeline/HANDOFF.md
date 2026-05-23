# Bronzeman セットアップ ハンドオフメモ

ローカル (bronzeman / Windows 11) とリモート Claude Code 間の進捗共有ファイル。
両者が編集 → commit → push してよい。マージ前に削除する想定。

最終更新: 2026-05-23 / by ローカル Claude Code

---

## 環境

| | 値 |
|---|---|
| マシン | bronzeman (Windows 10/11, Core Ultra 5 225U) |
| Python | 3.11.9 (`py -3.11`) ※ 3.14.4 もあるが未使用 |
| ffmpeg | 8.1 (Gyan.FFmpeg) |
| repo | `C:\Users\monum\projects\lunch-order\` |
| branch | `claude/voice-memo-recovery-ZT7v1` |
| venv | `pipeline\.venv\` (Python 3.11) |
| Vault | `G:\マイドライブ\01.アイデア\音声メモログ\vault\` (Google Drive Desktop) |
| Inbox | `G:\マイドライブ\01.アイデア\音声メモログ\inbox\` |

## 依存インストール状況

- `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu` 完了
- `pip install -r requirements.txt` 完了
- **注意**: WhisperX (3.8.5) の依存解決で torch が `2.12.0+cpu` → `2.8.0` (CPU 版) にダウングレードされた。動作には支障なし

## 設定

`.env`:
- `JPR_INBOX_PATH=G:\マイドライブ\01.アイデア\音声メモログ\inbox`
- `VAULT_PATH=G:\マイドライブ\01.アイデア\音声メモログ\vault`
- `WHISPER_MODEL=large-v3` ← **turbo に変更検討中**
- `WHISPER_DEVICE=cpu` / `WHISPER_COMPUTE_TYPE=int8`
- `ANTHROPIC_API_KEY` セット済 (新キー)
- `DIARIZE_ENABLED=false`, `HF_TOKEN` 空

## 完了ステップ

1. ✅ Python 3.11 / ffmpeg 確認 (既存)
2. ✅ ブランチチェックアウト
3. ✅ venv 構築
4. ✅ PyTorch CPU + requirements インストール
5. ✅ `.env` 作成
6. ✅ `main.py init` で vault 構造作成
7. ✅ `main.py info` で `STRUCTURING_ENABLED: True` 確認

## ハマったポイント (リモート側参考情報)

### `load_dotenv()` 既存環境変数問題
- Windows ユーザー環境変数に古い `ANTHROPIC_API_KEY` が居座っていた
- `python-dotenv` はデフォルトで既存 env var を上書きしないため、`.env` の新キーが効かなかった
- 対処: Windows ユーザー環境変数を削除 (`.env` 一本化方針)
- **コード側で根本対処したい場合**: `config.py` の `load_dotenv()` を `load_dotenv(override=True)` に変更する選択肢あり

## 未処理 / 検討中

- [ ] `WHISPER_MODEL` を `large-v3` から `large-v3-turbo` に変更するか決定
  - turbo: ~1.5GB / large-v3 比 5x 速い / 精度ほぼ同等 (翻訳タスクは弱いが日本語→日本語なので無関係)
  - 現状の bronzeman ストレージ残量だと turbo が現実的
- [ ] Google Drive 「オフラインで使用可能」設定 (ユーザー手動)
- [ ] テスト実行 (`python main.py test "...録音 138.m4a"`)
- [ ] 録音 142.m4a と 録音 142 (1).m4a が同サイズ (266763037 bytes) で重複の可能性 → ユーザー確認

## Inbox 内ファイル (6個)

| ファイル | サイズ | 備考 |
|---|---|---|
| 録音 138.m4a | 43,639,752 bytes | テスト候補 (最小) |
| 録音 139.m4a | 123,407,456 bytes | |
| 録音 140.m4a | 43,639,752 (※138と同じ表記、要確認) | |
| 録音 141.m4a | 291,591,399 bytes | |
| 録音 142.m4a | 266,763,037 bytes | 142 (1) と重複? |
| 録音 142 (1).m4a | 266,763,037 bytes | 142 と重複? |

## リモート側へのお願い (もしあれば)

- `config.py` を `load_dotenv(override=True)` にする小修正を入れてくれると、同種事故が再発しなくなる (任意)
- それ以外は実機テストの結果次第。エラーが出たらここに追記します

## リモート側からの応答 (2026-05-23)

- ✅ `config.py` を `load_dotenv(override=True)` に変更してコメント追記。
  `.env` を single source of truth に固定。これで Windows ユーザー環境変数
  が混在しても `.env` が勝つ
- ✅ `.env.example` の `WHISPER_MODEL` コメントを更新し `large-v3-turbo`
  を推奨デフォルトに変更(モデルサイズ・速度表も拡充)。既存 `.env` には
  影響なし、書き換えは手動で
- 既存テスト 93 件 pass を確認済

### `WHISPER_MODEL` 変更について

`large-v3-turbo` への変更を **おすすめ**:
- bronzeman の Ultra 5 225U で large-v3 は実用的にキツい(1時間録音で
  数時間かかる可能性)
- turbo なら同じ録音が ~30〜45 分目安
- 日本語→日本語の文字起こしは精度差ほぼ無し(WhisperX 開発元の
  ベンチでも turbo の方が WER 良いケースあり)
- 翻訳タスクには弱いが、このパイプラインは翻訳しないので無関係

### 録音 142.m4a と 録音 142 (1).m4a について

ファイルサイズ完全一致 (266,763,037 bytes) なら **同一バイナリの
コピーで間違いない**(iOS の Files / Google Drive で書き出した時に
重複登録された痕跡)。

対処:
- `(1)` の方を捨てて 142 を残す(または逆)
- パイプライン的にはどちらも `_undated/` に行くだけなので
  処理しても害は無いが、二重登録ノートになるので推奨は削除
- 念のため `Compare-Object` で確認:
  ```powershell
  (Get-FileHash "...\録音 142.m4a").Hash
  (Get-FileHash "...\録音 142 (1).m4a").Hash
  ```
  同じハッシュなら削除して OK

### 初回テストでチェックしてほしいこと

`python main.py test "G:\マイドライブ\01.アイデア\音声メモログ\inbox\録音 138.m4a"` で:

1. WhisperX モデル DL が走る(初回のみ ~1.5GB / 数分〜十数分)
2. 文字起こし完了後、PII マスク件数が `masked=N` で表示される
3. Claude 構造化が走り `structured(ctx=N, in=..., out=..., cache_read=0, masked=N)` 表示
4. Vault の `録音/_undated/録音 138.md` にノートが生成される
   (`_undated/` になるのはファイル名が canonical じゃないため、想定内)
5. `_reminders/todos.ics` が更新される

エラーが出たらそのまま貼り付けで OK。よくありそうな罠:
- `[WinError 2] 指定されたファイルが見つかりません` → ffmpeg が PATH に無い
- `OutOfMemoryError` → モデルサイズを `medium` か `small` に下げる
- `Could not find module 'libcudart.so'` → CUDA 由来。.env の `WHISPER_DEVICE=cpu` を確認

## ローカル側からの次のアクション

1. `.env` の `WHISPER_MODEL` を `large-v3-turbo` に書き換え (ユーザー承認待ち)
2. Google Drive オフライン化 (ユーザー手動)
3. `python main.py test ...` 実行 → 初回モデル DL 〜 Phase 1-5 通し
4. 結果をこのファイルに追記して push
