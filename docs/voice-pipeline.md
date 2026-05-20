# 業務録音処理パイプライン 設計仕様書

> 浦安市市民スポーツ課・遠藤啓祐の業務録音(電話・対面)を、**Apple Watch 録音 → iCloud同期 → 自動Drive投入** → 構造化された日次まとめまで自動処理するパイプライン。Claude Code 実装用の指針ドキュメント。

最終更新: 2026-05-20

-----

## 1. 目的と背景

### 現状の問題

- 業務中に発生する電話・対面の会話を、iPhoneの文字起こしアプリで貯めているが、それを処理するのに「Claudeにペタペタ貼り付ける」運用になっており非効率
- 既存のボイスメモShortcut(Google Forms経由)は途中で頓挫(Forms POSTのクエリパラメータ未設定で実質動作せず)
- 1日の中で 10〜15 トピック(電話・打ち合わせ)が混在しており、生の文字起こしから手作業で会話単位に切り分けるのが負担

### ゴール

- **Apple Watch で録音 → タップ操作なしで** 数分〜数十分後にDriveに**会話単位で構造化された日次まとめ**が並ぶ
- ToDoは Google Sheets の専用タブに自動追記
- iPhoneに溜まったバックログも同じ inbox に放り込めば順次処理される

### 録音デバイス前提

**主:** Apple Watch のボイスメモアプリ(片手で起動できる、相手の前でも目立たない)
**従:** iPhone のボイスメモアプリ(Watch が手元にない / 長時間案件)

Apple Watch で録音した内容は iCloud 経由で iPhone のボイスメモアプリに自動同期される(数十秒〜数分の遅延あり)。Shortcut/Automation はすべて iPhone 側で動作する。

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

### 2.2 シンプルさ優先

- iPhone 側のロジックは Automation 1個に集約(タップ不要)。手動 Shortcut はフォールバック用
- 処理本体は ThinkPad 側に集約。1箇所だけ動けばよい状態に
- 既存の GAS / Sheets パイプライン(短尺ボイスメモ用)とは別系統。共通化は将来検討

### 2.3 段階的構築

Phase 1〜5に分け、各Phase単独で価値が出る形にする。Phase 1+3だけでも「ペタペタ貼る」運用から脱却可能。

### 2.4 「全部とりあえずinboxに入れる」前提

Automation で自動投入される以上、テスト録音・誤起動・無音・私的会話も混ざる。**inbox の入口側で軽くフィルタ(長さ・無音率)し、本格的な絞り込みは Claude API 段で「業務に関係ない会話は出力しない」プロンプトで吸収する**設計とする。

-----

## 3. アーキテクチャ全体図

```
┌─────────────────────────────────────────────────────────────┐
│ Apple Watch (主) / iPhone (従)                               │
│   標準ボイスメモアプリで録音                                  │
│         │                                                     │
│         ▼ iCloud 自動同期(数十秒〜数分)                     │
│   iPhone のボイスメモアプリに新規アイテムが出現               │
│         │                                                     │
│         ▼ Personal Automation「新規ボイスメモ → Drive保存」  │
│   Google Drive: ボイス録音/inbox/YYYYMMDD_HHMMSS.m4a         │
│   (手動フォールバック: 共有シート → Shortcut「録音をinboxへ」)│
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
│   ① faster-whisper large-v3 (ローカル)                      │
│      → タイムスタンプ付き文字起こし                          │
│      ※ initial_prompt に浦安市・市民スポーツ課の用語集を投入  │
│         │                                                     │
│         ▼                                                     │
│   ② pyannote-audio (ローカル、HFトークン使用) ※Phase 2      │
│      → 話者ラベル(Speaker_A, Speaker_B, ...)                │
│      ※ Apple Watch 録音はモノラル/距離差小で精度不安定。     │
│        実データで効果を確認してから導入                       │
│         │                                                     │
│         ▼                                                     │
│   ③ アライメント: 話者ラベル付き文字起こし                  │
│         │                                                     │
│         ▼                                                     │
│   ④ PIIマスキング層                                          │
│      電話番号・メール・特定パターンを伏字化                  │
│         │                                                     │
│         ▼                                                     │
│   ⑤ Claude API (構造化要約・ToDo抽出)                       │
│      入力: マスク後の話者付き文字起こし                      │
│      出力: JSON(トピック分割・相手・要点・ToDo)            │
│      ※ 業務外の会話は空配列で返すよう指示                    │
│         │                                                     │
│         ▼                                                     │
│   ⑥ Markdown生成 + Sheets追記                                │
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

### 4.1 iPhone 側 - Automation 主案 + Shortcut フォールバック

#### 4.1.1 Personal Automation「新規ボイスメモ → inbox」(主案)

**目的:** Apple Watch で録音 → iCloud 同期 → タップなしで Drive inbox に自動投入。

**設定場所:** iPhone「ショートカット」アプリ → オートメーション → 個人用オートメーション

**トリガー:**
- iOS の Personal Automation には「新規ボイスメモ作成時」の直接トリガーは存在しない
- 代替案 A: ボイスメモアプリを開いたとき/閉じたとき → 直近の未処理アイテムを Drive 保存
- 代替案 B: Apple Watch のショートカット起動を組み合わせ、録音終了時にショートカット側から手動キック(タップは1回)
- 代替案 C: iCloud Drive の特定フォルダ書き込みをトリガーにする回避策

→ **実装着手時に iOS 最新仕様を確認して決定。動かなければ §4.1.2 の手動 Shortcut にフォールバック。**

**アクション構成(候補):**
1. ボイスメモから最新アイテムを取得
2. 既に処理済みかチェック(直近処理ファイル名を iCloud のメモに記録など)
3. ファイルを保存 → `Google Drive / ボイス録音 / inbox /`
4. ファイル名: `YYYYMMDD_HHMMSS_<元ファイル名>.m4a`
5. (オプション)通知「inboxへ送信」

#### 4.1.2 手動 Shortcut「録音をinboxへ」(フォールバック)

**目的:** Automation が暴発しない/動かない場合の、共有シートからの 2タップ投入。

**アクション構成(3ステップ):**
1. 共有シートから受け取る(オーディオファイル)
2. ファイルを保存 → `Google Drive / ボイス録音 / inbox /`
3. 通知「録音をinboxに保存しました」を表示

**現行Shortcutからの変更点:**
- ❌ オーディオファイルをテキストに文字起こし → 削除
- ❌ 変数設定 → 削除
- ❌ Forms URL の内容を取得 → 削除
- ✅ ファイル保存(Drive) → 新規追加

### 4.2 Driveフォルダ構造

```
ボイス録音/
├── inbox/        ← Automation/Shortcutが保存。未処理ファイル
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
- GPU: Intel Arc(統合) → faster-whisper は CPUモードで運用想定(Intel Core Ultra 5 で large-v3 が実用速度)

#### 4.3.2 主要ライブラリ

|用途        |ライブラリ                      |備考                |
|----------|---------------------------|------------------|
|Drive操作   |`google-api-python-client` |サービスアカウント認証推奨     |
|ファイル監視    |`watchdog`                 |リアルタイム検知          |
|軽フィルタ     |`pydub` / `librosa`        |長さ・RMS判定          |
|文字起こし     |`faster-whisper`           |`large-v3` モデル    |
|話者分離      |`pyannote.audio`           |Phase 2、HFトークン要   |
|PIIマスキング  |`re` + `spacy` + `ja_ginza`|正規表現+固有名詞認識       |
|Claude API|`anthropic`                |公式SDK             |
|Sheets操作  |`gspread`                  |OAuth or サービスアカウント|

#### 4.3.3 ⓪ 軽フィルタ(Automation時代の新規ステップ)

Automation で全録音が流れ込むので、Whisper を回す前に明らかなノイズを除外する。

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

#### 4.3.4 faster-whisper 設定

```python
from faster_whisper import WhisperModel

model = WhisperModel(
    "large-v3",
    device="cpu",
    compute_type="int8",   # CPU運用時はint8が高速
    cpu_threads=8,
)

INITIAL_PROMPT = (
    "浦安市 市民スポーツ課 遠藤 課長 係長 "
    "総合体育館 運動公園 屋内水泳プール ネットウィンチ "
    "指定管理者 入札 契約検査 業務委託料 修繕料 "
    # …用語集として別ファイル管理し、ここに展開
)

segments, info = model.transcribe(
    audio_path,
    language="ja",
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500),
    word_timestamps=True,
    initial_prompt=INITIAL_PROMPT,
)
```

#### 4.3.5 pyannote-audio 設定(Phase 2、要効果検証)

```python
from pyannote.audio import Pipeline

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=os.environ["HF_TOKEN"],
)

diarization = pipeline(audio_path)
# → 話者セグメント (start_time, end_time, speaker_label)
```

**Apple Watch 録音の懸念:**
- モノラル・帯域狭め・自分と相手の距離が近い → 話者分離が不安定になりやすい
- Phase 1+3 で1〜2週間運用してから「話者ラベル無しでも要約品質は十分か」を判断
- 不要と判断したら Phase 2 はスキップ

#### 4.3.6 PIIマスキング戦略

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

#### 4.3.7 Claude API 構造化プロンプト(雛形)

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

#### 4.3.8 出力Markdown形式

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
|**1**|手動 Shortcut + Drive inbox + 軽フィルタ + faster-whisper|録音を放り込んだら、生の文字起こしテキストがDriveに出る|半日    |
|**1.5**|Personal Automation 化(タップ不要)               |Apple Watch 録音が同期後に自動で inbox に入る|半日    |
|**2**|pyannote-audio ローカル組み込み(要効果検証)         |話者ラベルが付いて、Phase 1+3 比で要約品質が明確に向上 |1日    |
|**3**|Claude APIで構造化Markdown生成                       |`業務記録/YYYY-MM-DD.md` が自動生成される |半日    |
|**4**|PIIマスキング層追加 + Sheets ToDo同期                    |マスク後にClaude APIへ、ToDoが別シートに溜まる|1日    |
|**5**|Reminders連携、エラー処理、再実行UI                        |期限付きToDoがApple Remindersに     |余裕がある時|

**Phase 1+3 でMVP完成。** ペタペタ貼る運用はここで卒業できる。Phase 1.5 で完全自動化、Phase 2,4 は品質向上、Phase 5 は運用最適化。

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

# Hugging Face (pyannote)
HF_TOKEN=hf_xxxxxxxxxxxxxxxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-opus-4-7

# パイプライン設定
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cpu
POLLING_INTERVAL_SECONDS=900
SKIP_DURATION_THRESHOLD_S=10
SKIP_SILENCE_RATIO=0.95
```

-----

## 7. コスト試算(月額)

|項目                  |金額           |備考                      |
|--------------------|-------------|------------------------|
|pyannote.ai クラウド版 解約|**-¥3,000**  |ローカル版に移行                |
|OpenAI Whisper API  |¥0           |使わない(faster-whisperローカル)|
|Anthropic Claude API|+¥500〜1,500  |構造化要約のみ、Automation化で件数↑ |
|Google Drive/Sheets |¥0           |既存枠内                    |
|**差し引き**            |**既存より下がる方向**|                        |

-----

## 8. オープン論点(実装中に判断)

- [ ] **Apple Watch → iPhone 同期完了の検知方法**(Automationトリガーが直接対応していないため代替が必要)
- [ ] **Automation で同じファイルを二重投入しない方法**(処理済みファイル名を iCloud メモ/ローカルに記録)
- [ ] 録音ファイル名規則: Shortcut側で日時付与するか、Drive側のメタデータに任せるか
- [ ] 軽フィルタの閾値(10秒・無音95%)は実データで調整
- [ ] PIIマスキングで「自分(遠藤)」の発言は伏字化するか → 不要で確定
- [ ] 雑談・私的内容のフィルタリング基準(Claudeプロンプトで吸収、別ステップは作らない方針で確定)
- [ ] 既存ボイスメモパイプライン(短尺・GAS経由)との統合タイミング
- [ ] 1日の業務終了後に Slack/メール通知で「本日のまとめできました」リンクを送るか
- [ ] バックログ(過去の文字起こし)の一括取込みUI
- [ ] Apple Watch 録音のサンプリングレート / モノラル品質が Whisper 精度に与える影響を初週で実測

-----

## 9. リスクと緩和策

|リスク                        |緩和策                                            |
|---------------------------|-----------------------------------------------|
|ThinkPad が長期間オフ → 録音が溜まる   |inbox に貯まり続けるだけなので、起動時に順次処理されればOK              |
|**Apple Watch → iPhone iCloud同期の遅延**|Drive投入タイミングが録音から数十秒〜数分ずれる前提で運用。即時性が必要な案件はiPhone直接録音|
|**Automation 暴発による雑音流入**|軽フィルタ(⓪)+ Claudeプロンプトで業務外を空配列に寄せる二段構え|
|**Apple Watch 録音の音質**|モノラル・帯域狭め。faster-whisper large-v3 は耐えるが、`initial_prompt` で業務用語を必ず投入。重要案件は iPhone 録音を選択|
|PIIマスキング漏れ                 |段階的に正規表現と辞書を拡充、運用ログでチェック                       |
|Claude API のJSON出力フォーマット崩れ |`response_format` 指定、パース失敗時は再試行 + raw出力をfailedへ|
|faster-whisper の精度不足       |業務固有用語の `initial_prompt` を辞書化(浦安市・市民スポーツ課の用語集) |
|pyannote-audio の話者ラベルが安定しない|話者数の事前指定パラメータを活用、Apple Watch録音では効果限定的なのでPhase 2は要検証 |

-----

## 10. 着手手順(Claude Code セッション開始時のチェックリスト)

1. プロジェクトフォルダ作成: `~/projects/voice-pipeline/`
2. Python 仮想環境セットアップ(`uv` or `venv`)
3. `requirements.txt` 作成
4. `.env` テンプレ作成、必要なAPIキー取得
5. Google Cloud Console でサービスアカウント作成、Drive/Sheets共有設定
6. Hugging Face トークン取得、pyannote の利用規約に同意(Phase 2用、後回し可)
7. Phase 1 のスクリプト雛形作成: `pipeline/phase1_transcribe.py`
8. iPhone Shortcut の改修(手動版を先に動かす、§4.1.2)
9. テスト用音声(Apple Watch 録音を実機で1〜2件)で end-to-end 動作確認
10. Phase 1.5 として Automation を構築(§4.1.1)
11. cron / watchdog 常駐化

-----

以上。実装はこれをコンテキストとしてClaude Codeへ渡す前提。各Phase完了時にこの仕様書も更新していく。
