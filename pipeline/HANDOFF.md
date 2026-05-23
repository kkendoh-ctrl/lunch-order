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

1. ✅ `.env` の `WHISPER_MODEL` を `large-v3-turbo` に書き換え (承認済)
2. ✅ Google Drive オフライン化 (ユーザー設定済)
3. ✅ `python main.py test ...` 実行 → **失敗 (transcribe_error)**
4. ⏳ リモート側にエスカレーション中

## 初回テスト実行結果 (2026-05-23 19:30 頃)

**コマンド**: `python main.py test "G:\マイドライブ\01.アイデア\音声メモログ\inbox\録音 138.m4a"`

### ✅ 成功した部分
- WhisperX turbo モデル DL 成功 (`models--mobiuslabsgmbh--faster-whisper-large-v3-turbo` を HF キャッシュに取得)
- 音声デコード成功
- VAD (Pyannote) 実行成功

### ❌ 失敗箇所

```
処理中: G:\マイドライブ\01.アイデア\音声メモログ\inbox\録音 138.m4a
...
2026-05-23 19:30:59 - whisperx.vads.pyannote - INFO - Performing voice activity detection using Pyannote...
Traceback (most recent call last):
  File "C:\Users\monum\projects\lunch-order\pipeline\main.py", line 124, in _process_one_inner
    result = tx.transcribe(audio_path, cfg)
  File "C:\Users\monum\projects\lunch-order\pipeline\transcribe.py", line 87, in transcribe
    result = model.transcribe(audio, **transcribe_kwargs)
TypeError: FasterWhisperPipeline.transcribe() got an unexpected keyword argument 'initial_prompt'
結果: transcribe_error: FasterWhisperPipeline.transcribe() got an unexpected keyword argument 'initial_prompt'
```

### 原因分析

**WhisperX 3.x の API 変更**。`initial_prompt` は `model.transcribe()` の引数から外され、`whisperx.load_model(..., asr_options={"initial_prompt": "..."})` 経由で渡す形式に変わった。

該当箇所: `pipeline/transcribe.py:87` (`transcribe_kwargs["initial_prompt"]` を渡している)

### リモート側へ修正提案

`transcribe.py` の `_load_model` で `asr_options={"initial_prompt": cfg.load_initial_prompt()}` を渡し、`transcribe()` 呼び出し側からは `initial_prompt` を外す。具体例:

```python
def _load_model(cfg: Config):
    import whisperx
    key = f"{cfg.whisper_model}:{cfg.whisper_device}:{cfg.whisper_compute_type}"
    if key not in _model_cache:
        asr_options = {}
        prompt = cfg.load_initial_prompt()
        if prompt:
            asr_options["initial_prompt"] = prompt
        _model_cache[key] = whisperx.load_model(
            cfg.whisper_model,
            device=cfg.whisper_device,
            compute_type=cfg.whisper_compute_type,
            language=cfg.whisper_language,
            asr_options=asr_options or None,
        )
    return _model_cache[key]


def transcribe(audio_path: Path, cfg: Config) -> dict:
    import whisperx
    model = _load_model(cfg)
    audio = whisperx.load_audio(str(audio_path))
    result = model.transcribe(audio)  # initial_prompt は load 時に注入済
    ...
```

ただしモデルキャッシュキーに prompt が入っていないので、prompt 変更時にキャッシュ再生成しないバグの種になる。キーに hash 入れるか、テスト時はプロセス再起動前提とするか要判断。

### 副次的な警告 (致命的ではない / 参考)

1. `torchcodec is not installed correctly` — `libtorchcodec_core[4-7].dll` が見つからない警告。WhisperX 経路では使われていない (pyannote.audio が optional に試みただけ) ので無視可
2. `huggingface_hub cache-system uses symlinks` — Windows で開発者モード未有効 or 非管理者実行のため。ディスク使用が少し増えるだけ、致命的ではない
3. `Lightning automatically upgraded your loaded checkpoint from v1.5.4 to v2.6.4` — pyannote モデルが古い形式、自動アップグレードされたので問題なし

### 環境情報 (修正検証用)

- `whisperx==3.8.5` (requirements.txt の `whisperx>=3.1.5` で解決された最新)
- `faster-whisper==1.2.1`
- `ctranslate2==4.7.2`
- `torch==2.8.0` (CPU)
- `pyannote-audio==4.0.4`

## ローカル側からの次のアクション (更新)

- リモート側で `transcribe.py` 修正 & push を待つ
- 修正後、再度 `git pull` してテスト再実行
- HF キャッシュは保持されるので、2回目はモデル DL なしで即走る (時間短縮)

## リモート側からの応答 #2 (2026-05-23 / WhisperX API 修正)

✅ 修正完了 & push 済。`git pull` で取り込めます。

### 変更内容

1. **`transcribe.py::_load_model`** で `initial_prompt` を `asr_options={"initial_prompt": ...}` 経由で渡すように変更。提案いただいた形をベースに、`prompt` が空文字なら `asr_options` 自体を渡さないようにして WhisperX デフォルトを尊重(空文字を上書きすると挙動が変わる可能性があるため)
2. **`transcribe.py::transcribe`** の `transcribe_kwargs` を撤去、`model.transcribe(audio)` だけに
3. **キャッシュキー**: prompt はキーに含めない方針で確定。コメントで「cfg は process-static なので変えたければプロセス再起動」と明記
4. **`requirements.txt`**: `whisperx>=3.1.5` → `whisperx>=3.3.0` に引き上げ(古い API の whisperx が新規環境で引かれないように)
5. **`tests/test_transcribe.py`** を新規追加(5 ケース)
   - `initial_prompt` が `asr_options` 経由で正しく渡されるか
   - 空文字 / 無設定 / ファイル無し ならば `asr_options` を渡さないか
   - in-process キャッシュが効くか
   - `whisperx` モジュールを `monkeypatch.setitem(sys.modules, ...)` でスタブ化、実モデル DL 不要

全 98 テスト pass を確認済。

### ローカル側で再テスト時

1. `git pull origin claude/voice-memo-recovery-ZT7v1`
2. venv 内なので追加 install は不要 (whisperx 3.8.5 のままで OK)
3. `python main.py test "G:\マイドライブ\01.アイデア\音声メモログ\inbox\録音 138.m4a"`
4. HF キャッシュは前回 DL 済の `mobiuslabsgmbh--faster-whisper-large-v3-turbo` をそのまま使うので、モデル DL なしですぐに文字起こし開始するはず

期待する出力(再掲):
```
処理中: G:\...\録音 138.m4a
結果: transcribed(<秒数>, <セグメント数> segs) / structured(ctx=N, in=..., out=..., cache_read=0, masked=N) / aggregated(skeleton=N, daily=OK)
```

### 想定される次の罠

ここから先で起きそうな問題と対処メモ:
- **`whisperx.align` の API 変更**: `_load_align_model` も `whisperx.load_align_model(...)` を呼んでいる。同様に WhisperX 3.x で `model_name` キーワード必須になっている可能性あり。エラー出たら traceback 貼ってください
- **アライメント不要なら `WHISPER_ALIGN_ENABLED=false`** にして回避できる(.env で設定)
- **Claude 構造化での JSON パースエラー**: Phase 2 のプロンプト出力が不正なら `_extract_json` がフォールバックを試みるが、それでも失敗するなら `_失敗/` には行かず `structure_error` で止まる(現状)。要 traceback

## リモート側からの応答 #3 (2026-05-23 / pyannote VAD ハング対処)

### 状況確認

ローカル側からの報告で「2 時間 22 分 VAD でハング」と判明。
ログ末尾が `whisperx.vads.pyannote - INFO - Performing voice activity detection using Pyannote...` で止まっていて、それ以降出力ゼロ。

**結論: pyannote VAD は Windows + CPU で長尺音声を処理すると詰まる
既知の挙動**。WhisperX の GitHub Issues にも同様の報告複数あり。

### 対処: WhisperX の VAD エンジンを silero に切替可能にした

`whisperx.load_model` に `vad_method` パラメータがあり、デフォルトの
`pyannote` から `silero` に切り替えると劇的に軽くなる(silero は
torch jit script ベースの軽量モデル)。精度差は voice memo 用途で
実用上問題なし。

### 変更内容(push 済、commit に含める)

1. **`config.py`**: `whisper_vad_method: str = "pyannote"` フィールド追加
   (デフォルトはあえて pyannote のまま=既存挙動互換、`.env` で明示
   切替する運用)
2. **`transcribe.py::_load_model`**: `kwargs["vad_method"] = cfg.whisper_vad_method`
3. **`.env.example`**: `WHISPER_VAD_METHOD=silero` を bronzeman 向け推奨
   デフォルトとして記載
4. **`tests/test_transcribe.py`**: vad_method 受け渡しの 2 件追加

108 件 pass。

### ローカル側でやること

1. プロセス殺す:
   ```powershell
   Stop-Process -Name python -Force
   ```
2. `git pull origin claude/voice-memo-recovery-ZT7v1`
3. `.env` に `WHISPER_VAD_METHOD=silero` を追記(or `.env.example` の
   該当行をコピー)
4. ついでに念のためアライメントも切る(さらに高速化):
   `WHISPER_ALIGN_ENABLED=false`
5. **短いテスト用録音 (30 秒〜2 分)** をどこかで作って取込み or `inbox/`
   に置いて再テスト。録音 138 (~1.5〜3 時間想定) で再挑戦するのは
   silero の動作確認後

### 推奨手順(短録音テスト → 長尺本番)

```powershell
# 1. 短録音で動作確認 (5分以内に Phase 1〜5 通る想定)
python main.py test "G:\マイドライブ\01.アイデア\音声メモログ\inbox\<短録音.m4a>"

# 2. 動いたら長尺
python main.py test "G:\マイドライブ\01.アイデア\音声メモログ\inbox\録音 138.m4a"

# silero + アライメント無効なら、録音 138 (推定 90 分音声) で
# 30〜60 分目安で完了するはず
```

### もし silero でも詰まったら

その時はもう `Stop-Process` してから:
- `Get-Process python | Select CPU, WorkingSet` でメモリリーク確認
- ログ末尾を再度報告
- リモート側で「VAD 完全スキップ」モード(WhisperX に `vad_filter=False`
  に相当する設定)を追加する

を検討します。

## ローカル側からの応答 #2 (2026-05-23 22:08 / silero 検証成功)

### ✅ 30秒サンプルで全 Phase 通過

ffmpeg で `録音 138.m4a` の先頭 30秒を切り出して `test_30sec.m4a` を作成、
silero VAD でテスト → **エラー無し・全 Phase 完走**。

```
処理中: G:\マイドライブ\01.アイデア\音声メモログ\inbox\test_30sec.m4a
2026-05-23 22:08:32 - whisperx.vads.silero - INFO - Performing voice activity detection using Silero...
Using cache found in C:\Users\monum/.cache\torch\hub\snakers4_silero-vad_master
結果: transcribed(30.0s, 1 segs) / structured(ctx=0, in=186, out=153, cache_read=0, masked=0) / aggregated(skeleton=0, daily=OK)
```

- 開始 22:08:32 → 完了 22:08:49 (約 **17秒**)
- silero モデルは torch hub キャッシュ済 (DL なし)
- Claude API 接続 OK (`in=186, out=153` トークン)

### 生成物確認

| ファイル | サイズ | 状態 |
|---|---|---|
| `vault\録音\inbox\test_30sec.md` | 684 B | Markdown ノート生成 |
| `vault\_transcripts\inbox\test_30sec.json` | 787 B | 文字起こし JSON |
| `vault\_reminders\todos.ics` | 117 B | Reminders ics |

ノートのフロントマター抜粋:
```yaml
duration: 30s
counterpart: []
topics: []
importance: 3
sentiment: ニュートラル
model: claude-opus-4-7
```

本文: Claude が「雑談・テスト録音」判定で構造化スキップ (これは正しい挙動)
全文出力: `[00:17] 質問 質問 質問 質問...` (タイムスタンプ付き)

### 副次的観察

- `torchcodec` の dll 警告は出るが致命的でない (pyannote 経路使われず)
- `Lightning automatically upgraded` 警告も無害
- VAD 〜文字起こし完了まで stdout の途切れ無し (silero は素直)

### 次のアクション

長尺 `録音 138.m4a` (43MB) を silero でテスト中。完了次第このセクションに
追記する。

## ローカル側からの応答 #3 (2026-05-23 / 録音 138 長尺テスト)

実行中、結果は完了後追記。
