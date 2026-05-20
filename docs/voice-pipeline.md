# 業務録音処理パイプライン 設計仕様書

> 浦安市市民スポーツ課・遠藤啓祐の業務録音(電話・対面)を、**Apple Watch + VoxRec での録音 → Google Drive 自動アップロード** → 構造化された日次まとめまで自動処理するパイプライン。Claude Code 実装用の指針ドキュメント。

最終更新: 2026-05-20

-----

## 1. 目的と背景

### 現状の問題

- 業務中に発生する電話・対面の会話を、iPhoneの文字起こしアプリで貯めているが、それを処理するのに「Claudeにペタペタ貼り付ける」運用になっており非効率
- 既存のボイスメモShortcut(Google Forms経由)は途中で頓挫(Forms POSTのクエリパラメータ未設定で実質動作せず)
- 1日の中で 10〜15 トピック(電話・打ち合わせ)が混在しており、生の文字起こしから手作業で会話単位に切り分けるのが負担

### ゴール

- **Apple Watch で1タップ録音 → 操作不要で** 数分〜数十分後にDriveに**会話単位で構造化された日次まとめ**が並ぶ
- ToDoは Google Sheets の専用タブに自動追記
- iPhoneに溜まったバックログも同じ inbox に放り込めば順次処理される

### 録音デバイス・アプリ前提

**録音デバイス:**
- **主:** Apple Watch(片手で起動、相手の前でも目立たない、iPhoneが手元になくても可)
- **従:** iPhone(Watchが手元にない / 長時間案件)

**録音アプリ:** **VoxRec**(iOS / watchOS、録音機能とクラウドバックアップ機能は無料)
- 標準ボイスメモアプリは使わない(理由:Personal Automation / Shortcut で確実に Drive 投入する経路が iOS の仕様変更に振り回されやすいため)
- VoxRec の自社AI文字起こし機能は **使わない**(設定で Off / 課金しない)。文字起こしは ThinkPad 側で実施
- 採用理由詳細は §11 を参照

-----

## 2. 設計原則

### 2.1 セキュリティ・PII保護(最重要)

業務録音には以下のような機微情報が含まれる:

- 業者との価格交渉(例: ネットウィンチ電動化 3,500万円スキーム)
- 利用者の個人情報(申請番号、電話番号、氏名)
- 内部関係者(同僚、課長、業者担当者)の実名
- 政治案件・市長関連の来庁者情報

**設計原則:**

1. **音声ファイルは可能な限りローカル(ThinkPad)で処理し、クラウドAPIに送らない**
2. **テキスト化された後、Claude API送信前にPIIマスキングを通す**
3. クラウドAPI事業者のデータ取扱方針はAnthropicのみ確認済(API入力は学習に使わず短期保持)。他社利用時は都度確認
4. **VoxRec の自社AI文字起こしは使わない**(音声がVoxRec/サードパーティに渡るのを避ける)。アプリは録音+Google Drive アップロード経路のみ利用

### 2.2 シンプルさ優先

- iPhone 側のロジックは VoxRec の設定だけ(Shortcut / Automation を書かない)
- 処理本体は ThinkPad 側に集約。1箇所だけ動けばよい状態に
- 既存の GAS / Sheets パイプライン(短尺ボイスメモ用)とは別系統。共通化は将来検討

### 2.3 段階的構築

Phase 1〜5に分け、各Phase単独で価値が出る形にする。Phase 1+3だけでも「ペタペタ貼る」運用から脱却可能。

### 2.4 「全部とりあえずinboxに入れる」前提

VoxRec で録音すれば自動的に Drive に入る運用なので、テスト録音・誤起動・無音・私的会話も混ざる。**inbox の入口側で軽くフィルタ(長さ・無音率)し、本格的な絞り込みは Claude API 段で「業務に関係ない会話は出力しない」プロンプトで吸収する**設計とする。

-----

## 3. アーキテクチャ全体図

```
┌─────────────────────────────────────────────────────────────┐
│ Apple Watch (主) / iPhone (従)                               │
│   VoxRec で録音                                              │
│   (Watch はコンプリケーションから1タップ起動)                │
│         │                                                     │
│         ▼ 録音終了 → Watch から iPhone へ転送(数秒〜数十秒) │
│         ▼ VoxRec の自動バックアップで Google Drive へ        │
│   Google Drive: ボイス録音/inbox/YYYYMMDD_HHMMSS.m4a         │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼  (Drive API でThinkPadが取得)
┌─────────────────────────────────────────────────────────────┐
│ ThinkPad (bronzeman) - Python 常駐 or cron                  │
│                                                              │
│   watchdog / cron(15分) → 新規ファイル検知                  │
│         │                                                     │
│         ▼                                                     │
│   ⓪ 軽フィルタ: 長さ < 10s / 無音率 > 95% → skipped/ へ       │
│         │                                                     │
│         ▼                                                     │
│   ① WhisperX (ローカル)                                      │
│      → タイムスタンプ付き文字起こし(+ Phase 2 で話者ラベル) │
│      ※ initial_prompt に浦安市・市民スポーツ課の用語集を投入  │
│         │                                                     │
│         ▼                                                     │
│   ② PIIマスキング層                                          │
│      電話番号・メール・特定パターンを伏字化                  │
│         │                                                     │
│         ▼                                                     │
│   ③ Claude API (構造化要約・ToDo抽出)                       │
│      入力: マスク後の文字起こし                              │
│      出力: JSON(トピック分割・相手・要点・ToDo)            │
│      ※ 業務外の会話は空配列で返すよう指示                    │
│         │                                                     │
│         ▼                                                     │
│   ④ Markdown生成 + Sheets追記                                │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 出力                                                          │
│   Drive: 業務記録/2026-05-20.md  ← 1日分まとめ              │
│   Sheets: 業務記録ToDo タブ      ← アクション管理           │
│   Drive: ボイス録音/processed/   ← 元ファイル移動           │
│   Drive: ボイス録音/skipped/     ← 短尺・無音               │
└─────────────────────────────────────────────────────────────┘
```

-----

## 4. コンポーネント詳細

### 4.1 iPhone / Apple Watch 側 - VoxRec の設定

**目的:** Apple Watch で録音 → ユーザー操作なしで Google Drive inbox に到着させる。iOS の Shortcut / Personal Automation を一切書かない。

#### 4.1.1 iPhone 側セットアップ

1. App Store から **VoxRec**(無料)をインストール
2. アプリを開いて、Settings → **Siri & Cloud Sync** → **Set up Backup Folder** をタップ
3. **Google Drive** を選択し、業務用 Google アカウントで認証
4. バックアップ先フォルダを `ボイス録音/inbox/` に指定
5. **Auto backup** を ON(録音停止時に自動アップロード)
6. **自社AI文字起こし機能(Live Transcription / Speech-to-Text)** を OFF
7. (任意)録音フォーマット: m4a, 44.1kHz, モノラル / 64kbps程度(後段の Whisper 入力として十分)

#### 4.1.2 Apple Watch 側セットアップ

1. Watch の文字盤を長押し → 編集 → コンプリケーションに **VoxRec** を追加
2. 文字盤を1タップ → 録音開始
3. もう1タップ → 停止 → 自動的に iPhone へ転送 → iPhone が Drive へアップロード

#### 4.1.3 録音時の注意

- VoxRec の **自社AI文字起こし(Live Dictation)を絶対に有効にしない**(音声が VoxRec の文字起こしサーバに送られる)
- バックアップ完了通知が iPhone に出ることを最初の1週間は毎回確認(Drive に到着しているか目視)
- 録音中に「アップロード前提なので個人情報は最小限に」と意識づけ(=PIIマスキングは保険、運用で防ぐのが本筋)

### 4.2 Driveフォルダ構造

```
ボイス録音/
├── inbox/        ← VoxRec が保存。未処理ファイル
├── processing/   ← 処理中(ロック用)。任意
├── processed/    ← 処理完了後の元ファイル(月別サブフォルダ推奨)
│   ├── 2026-05/
│   └── ...
├── skipped/      ← 軽フィルタで除外(短尺・無音)。月別サブフォルダ
└── failed/       ← 処理失敗ファイル(リトライ用)

業務記録/
├── 2026-05-20.md
├── 2026-05-21.md
└── ...
```

### 4.3 ThinkPad バックエンド

#### 4.3.1 環境

- ThinkPad X13 Gen 6 "bronzeman"
- Windows 11 + WSL2 (Ubuntu) 推奨。Pythonをネイティブ運用するならPowerShell側でも可
- Python 3.11+
- GPU: Intel Arc(統合) → WhisperX は CPUモードで運用想定(Intel Core Ultra 5 で large-v3 が実用速度)

#### 4.3.2 主要ライブラリ

|用途        |ライブラリ                      |備考                |
|----------|---------------------------|------------------|
|Drive操作   |`google-api-python-client` |サービスアカウント認証推奨     |
|ファイル監視    |`watchdog`                 |リアルタイム検知          |
|軽フィルタ     |`pydub` / `librosa`        |長さ・RMS判定          |
|文字起こし+話者分離 |`whisperx`             |faster-whisper + pyannote を統合した完成品 |
|PIIマスキング  |`re` + `spacy` + `ja_ginza`|正規表現+固有名詞認識       |
|Claude API|`anthropic`                |公式SDK             |
|Sheets操作  |`gspread`                  |OAuth or サービスアカウント|

#### 4.3.3 ⓪ 軽フィルタ

VoxRec で全録音が流れ込むので、WhisperX を回す前に明らかなノイズを除外する。

```python
from pydub import AudioSegment

def should_skip(audio_path) -> tuple[bool, str]:
    audio = AudioSegment.from_file(audio_path)
    duration_s = len(audio) / 1000
    if duration_s < 10:
        return True, "too_short"
    # 無音率: -40dBFS 未満が95%以上
    silent_chunks = sum(1 for chunk in audio[::500] if chunk.dBFS < -40)
    if silent_chunks / (len(audio) / 500) > 0.95:
        return True, "mostly_silent"
    return False, ""
```

#### 4.3.4 WhisperX 設定(文字起こし + 話者分離を1本化)

faster-whisper と pyannote を別々に組まず、両者を統合済みの **WhisperX** を採用する。Phase 1 では `diarize=False` で文字起こしのみ、Phase 2 で `diarize=True` を有効化する。

```python
import whisperx

device = "cpu"
compute_type = "int8"

# 1. 文字起こし(Phase 1 から有効)
model = whisperx.load_model(
    "large-v3",
    device=device,
    compute_type=compute_type,
    language="ja",
)

INITIAL_PROMPT = (
    "浦安市 市民スポーツ課 遠藤 課長 係長 "
    "総合体育館 運動公園 屋内水泳プール ネットウィンチ "
    "指定管理者 入札 契約検査 業務委託料 修繕料 "
    # …用語集として別ファイル管理し、ここに展開
)

audio = whisperx.load_audio(audio_path)
result = model.transcribe(audio, initial_prompt=INITIAL_PROMPT)

# 2. アライメント(単語レベルタイムスタンプ)
align_model, metadata = whisperx.load_align_model(
    language_code="ja", device=device
)
result = whisperx.align(
    result["segments"], align_model, metadata, audio, device=device
)

# 3. 話者分離(Phase 2 で有効化、HF_TOKEN 要)
if DIARIZE_ENABLED:
    diarize_model = whisperx.DiarizationPipeline(
        use_auth_token=os.environ["HF_TOKEN"], device=device
    )
    diarize_segments = diarize_model(audio)
    result = whisperx.assign_word_speakers(diarize_segments, result)
```

**Apple Watch 録音特性に対する想定:**
- モノラル・帯域狭め・自分と相手の距離が近い → 話者分離が不安定になりやすい
- Phase 1+3 で1〜2週間運用してから「話者ラベル無しでも要約品質は十分か」を判断
- 不要と判断したら Phase 2 はスキップ可

#### 4.3.5 PIIマスキング戦略

**機械的にマスクするパターン:**

- 電話番号: `\d{2,4}-\d{2,4}-\d{4}` → `[電話番号]`
- メール: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` → `[メール]`
- 申請番号(7桁): `\b\d{7}\b` → `[申請番号]`
- 郵便番号: `\d{3}-\d{4}` → `[郵便番号]`

**spaCy/GiNZA で人名・組織名を検出して伏字化(オプション):**

- ただし業務文脈では「課長」「○○課」など固有名詞も意味を持つので、伏字化しすぎると要約品質が落ちる
- 推奨: 個人名は伏字化、組織・役職は残す
- 「許可リスト」方式: 浦安市・自身の課・既知の関係先(GoogleDriveから取得可)はマスクしない
- 自分(遠藤)の発言は伏字化しない(自分→自分なので冗長)

**マスク辞書:** `pii_dict.yaml` を別管理し、運用しながら拡充

#### 4.3.6 Claude API 構造化プロンプト(雛形)

```
以下はある業務日の音声を文字起こししたものです。話者ラベルとタイムスタンプ付き。
これを「会話単位」に分割し、それぞれについて構造化JSONで出力してください。

出力スキーマ:
{
  "date": "YYYY-MM-DD",
  "conversations": [
    {
      "start_time": "HH:MM:SS",
      "end_time": "HH:MM:SS",
      "topic": "短い見出し",
      "counterpart": "相手の名前や所属(不明なら null)",
      "category": "施設管理 / 入札契約 / システム業務 / 内部調整 / その他 のいずれか",
      "summary": "3-5文の要点",
      "todos": [
        {"text": "アクション内容", "due": "期限(あれば、なければ null)", "assignee": "self / 他者名"}
      ],
      "key_decisions": ["合意・決定事項のリスト"],
      "open_questions": ["未解決の論点"]
    }
  ]
}

注意:
- 会話の境界は話題の転換と相手の変化で判定
- **業務に関係しない私的な会話・雑談・テスト録音は出力に含めない(conversations を空にしてよい)**
- 不確実な情報は推測せず "(要確認)" と付記
- JSONのみ返す、Markdownや前置きは不要
```

参考: jessedc/claude-apple-voice-memos-skill の SKILL.md に同種のプロンプトがあるので、運用しながら良い表現を吸収する。

#### 4.3.7 出力Markdown形式

```markdown
# 業務記録 2026-05-20(水)

## 🔴 要対応・本日中

### 1. 大子さん 説明欄訂正
- **相手**: 大子さん(契約検査?)
- **時刻**: 14:30-14:35
- 要点: ...
- ToDo:
  - [ ] 手書きで「本来業務委託料で...」と訂正、システムは触らない

(以下、会話ごとに続く)

## 📋 本日のToDoまとめ
- [ ] (各会話から抽出した全ToDoのフラット一覧)
```

### 4.4 トリガー

**選択肢A: watchdog常駐(推奨)**

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# inboxフォルダ(ローカル同期 or Drive APIポーリング)を監視
# 新規ファイル検知 → 即処理
```

**選択肢B: Windowsタスクスケジューラ + Python script (15分間隔)**

PCを常時起動しない場合や、watchdog の負荷が気になる場合はこちら。Apple Watch 録音は短尺〜中尺が多く、15分の遅延でも体感問題なし。

-----

## 5. フェーズ計画

|Phase|内容                                             |完了条件                          |想定工数  |
|-----|-----------------------------------------------|------------------------------|------|
|**1**|VoxRec 設定 + Drive inbox + 軽フィルタ + WhisperX 文字起こし|Watchで録音したら数分後にDriveに生の文字起こしテキストが出る|半日    |
|**2**|WhisperX の話者分離フラグを有効化(要効果検証)        |話者ラベルが付いて、Phase 1+3 比で要約品質が明確に向上 |半日   |
|**3**|Claude APIで構造化Markdown生成                       |`業務記録/YYYY-MM-DD.md` が自動生成される |半日    |
|**4**|PIIマスキング層追加 + Sheets ToDo同期                    |マスク後にClaude APIへ、ToDoが別シートに溜まる|1日    |
|**5**|Reminders連携、エラー処理、再実行UI                        |期限付きToDoがApple Remindersに     |余裕がある時|

**Phase 1+3 でMVP完成。** ペタペタ貼る運用はここで卒業できる。Phase 2,4 は品質向上、Phase 5 は運用最適化。WhisperX 採用で Phase 2 は「フラグを立てるだけ」のコストになった。

-----

## 6. 設定値・環境変数

`.env` 例:

```
# Google
GOOGLE_SERVICE_ACCOUNT_JSON=path/to/service-account.json
DRIVE_INBOX_FOLDER_ID=xxxxxxxxxxxxxxxx
DRIVE_PROCESSED_FOLDER_ID=xxxxxxxxxxxxxxxx
DRIVE_SKIPPED_FOLDER_ID=xxxxxxxxxxxxxxxx
DRIVE_DAILY_OUTPUT_FOLDER_ID=xxxxxxxxxxxxxxxx
SHEETS_TODO_SHEET_ID=xxxxxxxxxxxxxxxx
SHEETS_TODO_TAB_NAME=ToDo

# Hugging Face (WhisperX 話者分離用、Phase 2 で必要)
HF_TOKEN=hf_xxxxxxxxxxxxxxxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-opus-4-7

# パイプライン設定
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cpu
DIARIZE_ENABLED=false
POLLING_INTERVAL_SECONDS=900
SKIP_DURATION_THRESHOLD_S=10
SKIP_SILENCE_RATIO=0.95
```

-----

## 7. コスト試算(月額)

|項目                  |金額           |備考                      |
|--------------------|-------------|------------------------|
|pyannote.ai クラウド版 解約|**-¥3,000**  |WhisperX(ローカル)に移行         |
|OpenAI Whisper API  |¥0           |使わない(WhisperXローカル)|
|VoxRec              |¥0           |録音+Driveバックアップは無料機能のみ利用|
|Anthropic Claude API|+¥500〜1,500  |構造化要約のみ、録音件数次第       |
|Google Drive/Sheets |¥0           |既存枠内                    |
|**差し引き**            |**既存より下がる方向**|                        |

-----

## 8. オープン論点(実装中に判断)

- [ ] 録音ファイル名規則: VoxRec 側で日時付与するか、Drive側のメタデータに任せるか
- [ ] 軽フィルタの閾値(10秒・無音95%)は実データで調整
- [ ] PIIマスキングで「自分(遠藤)」の発言は伏字化するか → 不要で確定
- [ ] 雑談・私的内容のフィルタリング基準(Claudeプロンプトで吸収、別ステップは作らない方針で確定)
- [ ] 既存ボイスメモパイプライン(短尺・GAS経由)との統合タイミング
- [ ] 1日の業務終了後に Slack/メール通知で「本日のまとめできました」リンクを送るか
- [ ] バックログ(過去の文字起こし)の一括取込みUI
- [ ] Apple Watch 録音のサンプリングレート / モノラル品質が Whisper 精度に与える影響を初週で実測
- [ ] VoxRec の Google Drive アップロード失敗時の検知・通知方法(アプリ通知頼みでよいか)
- [ ] VoxRec の無料機能制限が将来変わった場合の代替アプリ(RecorderHQ / Just Press Record + iCloud Drive)

-----

## 9. リスクと緩和策

|リスク                        |緩和策                                            |
|---------------------------|-----------------------------------------------|
|ThinkPad が長期間オフ → 録音が溜まる   |inbox に貯まり続けるだけなので、起動時に順次処理されればOK              |
|**Apple Watch → iPhone 転送遅延 / VoxRec の Drive アップロード遅延**|録音から Drive 到着まで数十秒〜数分の遅延を前提に運用。即時性が必要な案件は iPhone で直接 VoxRec 起動|
|**VoxRec の無料機能仕様変更 / サービス停止**|録音は標準 m4a なのでアプリ依存度は低い。代替候補(RecorderHQ / Just Press Record + iCloud Drive)を §8 に記録|
|**VoxRec の自社AI機能を誤ってON**|セットアップ後に必ず Off を確認。設定スクリーンショットを残す|
|**Apple Watch 録音の音質**|モノラル・帯域狭め。WhisperX large-v3 は耐えるが、`initial_prompt` で業務用語を必ず投入。重要案件は iPhone 録音を選択|
|PIIマスキング漏れ                 |段階的に正規表現と辞書を拡充、運用ログでチェック                       |
|Claude API のJSON出力フォーマット崩れ |`response_format` 指定、パース失敗時は再試行 + raw出力をfailedへ|
|WhisperX の精度不足           |業務固有用語の `initial_prompt` を辞書化(浦安市・市民スポーツ課の用語集) |
|WhisperX の話者ラベルが安定しない|Apple Watch録音では距離差が小さく難易度高め。Phase 2 は要効果検証、効果不十分なら無効のまま運用 |

-----

## 10. 着手手順(Claude Code セッション開始時のチェックリスト)

1. プロジェクトフォルダ作成: `~/projects/voice-pipeline/`
2. Python 仮想環境セットアップ(`uv` or `venv`)
3. `requirements.txt` 作成
4. `.env` テンプレ作成、必要なAPIキー取得
5. Google Cloud Console でサービスアカウント作成、Drive/Sheets共有設定
6. iPhone に VoxRec をインストール、Google Drive バックアップを設定(§4.1.1)
7. Apple Watch のコンプリケーションに VoxRec を配置(§4.1.2)
8. 試し録音1〜2件 → Drive `inbox/` に届くことを確認
9. Hugging Face トークン取得、pyannote の利用規約に同意(Phase 2用、後回し可)
10. Phase 1 のスクリプト雛形作成: `pipeline/phase1_transcribe.py`
11. テスト用音声で end-to-end 動作確認
12. cron / watchdog 常駐化

-----

## 11. 採用アプリの選定理由(VoxRec)

Apple Watch 録音アプリは複数あるが、本パイプラインの要件は次の通り:

1. Apple Watch から単独で録音できる
2. 録音ファイルが ThinkPad の届く場所(=Google Drive)に到着する
3. 音声がサードパーティAI(OpenAI等)に渡らない経路で実現できる
4. 日本語環境で問題なく動く
5. ランニングコストが低い

主な候補と評価:

|アプリ                |評価                                |
|--------------------|----------------------------------|
|VoxRec(採用)|**録音+Google Drive バックアップが無料**。Watch単独録音可・日本語自動句読点対応。自社AIは Off で運用可|
|Just Press Record|$4.99 買切り。Apple純正オンデバイス文字起こし内蔵で PII 的に最安全。**ただし保存先が iCloud Drive 限定** → Google Drive 主軸の本構成と相性悪|
|RecorderHQ|Google Drive 対応・Watch対応。日本語精度の評判が見つけにくく VoxRec 優先|
|Awesome Voice Recorder|月額$3.99〜。機能多いが料金体系が VoxRec より重い|
|Whisper Notes / MacWhisper|オフライン Whisper 内蔵で究極のプライバシー。**ただしファイル取り出しが面倒**でパイプラインへの接続コストが高い|
|Whisper Memos|録音→AI要約まで自動。**音声が OpenAI に送信される** → §2.1 の原則に反するため不採用|

将来 VoxRec の仕様変更や Google Drive 連携の不具合が発生した場合の差替候補は RecorderHQ → Just Press Record + iCloud Drive(パイプラインを iCloud 軸に書換) の順で検討する。

-----

以上。実装はこれをコンテキストとしてClaude Codeへ渡す前提。各Phase完了時にこの仕様書も更新していく。
