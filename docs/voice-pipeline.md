# 音声記憶パイプライン 設計仕様書

> Apple Watch + Just Press Record で録音 → iCloud Drive 経由で ThinkPad に到着 → WhisperX で文字起こし → Claude API で構造化・エンティティ抽出 → Obsidian Vault「音声記憶」に蓄積。業務と私的を切り離さず1つの知識ベースに統合する。

最終更新: 2026-05-23

-----

## 1. 目的と背景

### 現状の問題

- 業務中・私的場面の電話・対面・独り言を iPhone のアプリで貯めるだけになっている
- 既存の「Claudeにペタペタ貼り付ける」運用は非効率かつ蓄積されない
- 1日に 10〜20 件の会話・思考メモが混在し、後から「あの件どうなったっけ」が探せない
- **業務領域(契約・施設管理・人事)と私的領域(知的興味・家族・趣味)は実は地続き** で、強引に分けると失われる文脈がある

### ゴール

- **Apple Watch を1タップして録音** → 数分後に **Obsidian Vault に構造化されたノートとして自動追加**
- ノート同士が `[[人物]]` `[[トピック]]` `[[場所]]` で自動リンクされ、グラフビューで「誰の話」「何の連なり」が一目で見える
- ToDoは横串で1ファイルに集約、重要度の高い録音もリストアップ
- 業務/私的は分離せず1つの Vault に統合、タグで色分けする

### 録音デバイス・アプリ前提

**録音デバイス:**
- **主:** Apple Watch(コンプリケーションから1タップ、相手の前でも目立たない、iPhone 不要)
- **従:** iPhone(Watch が手元にない / 長時間案件 / AirPods 経由)

**録音アプリ:** **Just Press Record**(iOS / watchOS / macOS、$4.99 買い切り)
- 採用理由詳細は §11
- 自動文字起こし機能は **使わない**(使ってもよいが我々は WhisperX を使う)
- iCloud Drive の通常フォルダに `.m4a` を自動保存してくれる点が決め手

-----

## 2. 設計原則

### 2.1 セキュリティ・PII保護(最重要)

業務・私的どちらの録音にも機微情報が含まれる:

- 業務: 業者との価格交渉、利用者の個人情報、内部関係者の実名、政治案件
- 私的: 家族・友人の本名、健康情報、財務状況、固有の意見

**原則:**

1. **音声ファイルは ThinkPad ローカルで処理し、音声をクラウドAPIに送らない**
2. **テキスト化された後、Claude API送信前に PII マスキングを通す**
3. Just Press Record はオンデバイス処理のみ・データ収集なしを公言、Apple iCloud のみに保存
4. Anthropic API は入力を学習に使わず短期保持(確認済)

### 2.2 業務/私的を1つの Vault に統合

「これは業務」「これは私的」と入口で分けない。代わりに:

- 録音ノートに **複数タグ**を付ける(`#業務`, `#私的`, `#知的興味`, `#家族` など共存可)
- `[[]]` リンクは領域横断(例: `[[モルック大会]]` は業務でも私的でも同じノート)
- Obsidian のグラフビューで「業務トピックと私的トピックがどこで交差してるか」を可視化

### 2.3 シンプルさ優先

- 録音側のロジックは Just Press Record の設定だけ(Shortcut も Automation も書かない)
- 処理本体は ThinkPad に集約
- 既存の GAS / Sheets パイプライン(短尺ボイスメモ用)とは別系統

### 2.4 段階的構築

Phase 1〜5 に分け、各 Phase 単独で価値が出る形にする。Phase 1+2 だけで「ペタペタ貼る」運用から脱却可能。

### 2.5 「全部とりあえず拾う」前提

Just Press Record でタップすれば自動的に iCloud Drive に入る運用なので、テスト録音・誤起動・無音・私的雑談も混ざる。**入口側で軽くフィルタ(長さ・無音率)し、本格的な絞り込みは Claude プロンプトで「業務でも知的でもない雑談は要約しない」吸収する**設計とする。

-----

## 3. アーキテクチャ全体図

```
┌─────────────────────────────────────────────────────────────┐
│ Apple Watch (主) / iPhone (従)                               │
│   Just Press Record で録音                                   │
│   (Watch はコンプリケーションから1タップ起動)                │
│         │                                                     │
│         ▼ 録音終了 → Watch から iPhone へ自動転送            │
│         ▼ iPhone から iCloud Drive へ自動アップロード         │
│   iCloud Drive: Just Press Record/YYYY-MM-DD/HH-MM-SS.m4a   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼  (iCloud for Windows で同期)
┌─────────────────────────────────────────────────────────────┐
│ ThinkPad (bronzeman) - Python 常駐 or タスクスケジューラ    │
│                                                              │
│   ① watchdog → iCloudDrive\Just Press Record\ の新規検知    │
│         │                                                     │
│         ▼                                                     │
│   ② 軽フィルタ: 長さ < 10s / 無音率 > 95% → _skipped/       │
│         │                                                     │
│         ▼                                                     │
│   ③ WhisperX (ローカル)                                      │
│      → タイムスタンプ付き文字起こし                          │
│      ※ initial_prompt に業務用語+私的用語を投入              │
│         │                                                     │
│         ▼                                                     │
│   ④ PII マスキング層                                         │
│      電話・メール・申請番号・家族名等を伏字化                │
│         │                                                     │
│         ▼                                                     │
│   ⑤ Claude API (構造化・エンティティ抽出・要約)             │
│      入力: マスク後の文字起こし                              │
│      出力: JSON                                              │
│        - 1〜複数の「コンテキスト」に分割                     │
│        - 各コンテキスト: 要約 / ToDo / 人物 / トピック / 場所│
│        - 領域タグ(複数可): 業務/私的/知的興味/家族/健康など │
│        - 重要度スコア(1-5)                                  │
│      ※ 雑談は出力に含めない指示                              │
│         │                                                     │
│         ▼                                                     │
│   ⑥ Obsidian Vault に Markdown 書き込み                     │
│      - 録音/YYYY-MM-DD/HH-MM-SS.md (1録音=1ノート)          │
│      - 日次/YYYY-MM-DD.md に [[]] 集約                      │
│      - 人物/トピック/場所 ノートを存在しなければ自動生成     │
│      - 一覧/ToDo.md / 一覧/重要度高.md を再生成              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Obsidian Vault: iCloud Drive/音声記憶/                       │
│   iPhone / iPad / Mac / Windows どこからでも閲覧・編集可     │
│   グラフビューで知識マップが見える                            │
└─────────────────────────────────────────────────────────────┘
```

-----

## 4. コンポーネント詳細

### 4.1 Apple Watch / iPhone 側 - Just Press Record の設定

**目的:** Apple Watch で録音 → ユーザー操作なしで iCloud Drive の `Just Press Record/` フォルダに到着させる。

#### 4.1.1 iPhone 側セットアップ

1. App Store で **Just Press Record** ($4.99) を購入・インストール
2. 初回起動でマイクと音声認識のアクセスを許可
3. 設定 → **Cloud Storage** で **iCloud Drive** を選択(デフォルトでON)
4. (任意) **Transcription** は OFF にする(ThinkPad 側で WhisperX を使うため)
5. 録音テスト1件 → Files アプリで `iCloud Drive/Just Press Record/YYYY-MM-DD/HH-MM-SS.m4a` に到着するのを確認

#### 4.1.2 Apple Watch 側セットアップ

1. iPhone の Watch アプリ → 「文字盤ギャラリー」または現在の文字盤の編集
2. コンプリケーションスロットに **Just Press Record** を配置
3. Watch の文字盤を1タップ → 録音開始
4. もう1タップ → 停止 → Watch ローカルに保存 → 自動的に iPhone へ同期 → iCloud Drive へ

#### 4.1.3 録音時の注意

- **Watch の画面ロックで録音が停止**する(通知なし)。長尺案件は iPhone で録るか「常にオン」モードを有効化
- 録音中に Watch の別アプリを開くとキャンセルされる
- Watch → iPhone 同期遅延の報告あり。アプリ内の「未同期」リストを週1で確認、必要なら手動再送

### 4.2 iCloud Drive と iCloud for Windows

#### 4.2.1 フォルダ構造

```
iCloud Drive/
├── Just Press Record/             ← JPR が自動管理。触らない
│   ├── 2026-05-23/
│   │   ├── 13-39-19.m4a
│   │   └── 14-22-05.m4a
│   └── 2026-05-24/
│       └── ...
│
└── 音声記憶/                       ← Obsidian Vault (新規作成、§5 参照)
    └── (§5 のフォルダ構成)
```

#### 4.2.2 ThinkPad での同期

- ThinkPad に **iCloud for Windows** をインストール
- 「**iCloud Drive を File Explorer に同期**」を ON
- Windows 上では `C:\Users\<user>\iCloud Drive\` 配下に展開される
- WSL2 から触る場合は `/mnt/c/Users/<user>/iCloud Drive/` 経由

`Just Press Record/` と `音声記憶/` の両方が ThinkPad にも同期される。

### 4.3 ThinkPad バックエンド

#### 4.3.1 環境

- ThinkPad X13 Gen 6 "bronzeman"
- Windows 11 + WSL2 (Ubuntu) 推奨
- Python 3.11+
- GPU: Intel Arc(統合) → WhisperX は CPU モードで運用想定(Intel Core Ultra 5 で large-v3 が実用速度)

#### 4.3.2 主要ライブラリ

| 用途 | ライブラリ | 備考 |
|---|---|---|
| ファイル監視 | `watchdog` | iCloud Drive 配下を監視 |
| 軽フィルタ | `pydub` | 長さ・RMS判定 |
| 文字起こし | `whisperx` | faster-whisper + 単語アライメント |
| PIIマスキング | `re` + `spacy` + `ja_ginza` | 正規表現+固有名詞認識 |
| Claude API | `anthropic` | 公式SDK |
| YAML フロントマター生成 | `python-frontmatter` | Obsidian ノートの metadata |

#### 4.3.3 ② 軽フィルタ

Watch のタップミスや無音録音を除外する。

```python
from pydub import AudioSegment

def should_skip(audio_path) -> tuple[bool, str]:
    audio = AudioSegment.from_file(audio_path)
    duration_s = len(audio) / 1000
    if duration_s < 10:
        return True, "too_short"
    silent_chunks = sum(1 for chunk in audio[::500] if chunk.dBFS < -40)
    if silent_chunks / (len(audio) / 500) > 0.95:
        return True, "mostly_silent"
    return False, ""
```

除外したファイルは `_skipped/YYYY-MM/` に移動(分析対象から外すが残しておく)。

#### 4.3.4 ③ WhisperX 設定

```python
import whisperx

device = "cpu"
compute_type = "int8"

model = whisperx.load_model(
    "large-v3",
    device=device,
    compute_type=compute_type,
    language="ja",
)

# initial_prompt は業務用語+私的用語の両方を投入
INITIAL_PROMPT = open("prompts/whisper-initial-prompt.txt").read()

audio = whisperx.load_audio(audio_path)
result = model.transcribe(audio, initial_prompt=INITIAL_PROMPT)

# 単語レベルアライメント
align_model, metadata = whisperx.load_align_model(
    language_code="ja", device=device
)
result = whisperx.align(
    result["segments"], align_model, metadata, audio, device=device
)
```

話者分離(diarization)は Phase 5。Watch 録音はモノラル・距離差小で不安定化しやすいので、効果検証してから有効化。

#### 4.3.5 ④ PIIマスキング戦略

機械的にマスクするパターン:

- 電話番号: `\d{2,4}-\d{2,4}-\d{4}` → `[電話番号]`
- メール: 標準パターン → `[メール]`
- 申請番号(7桁): `\b\d{7}\b` → `[申請番号]`
- 郵便番号: `\d{3}-\d{4}` → `[郵便番号]`
- クレジットカード様の数字列 → `[番号]`

spaCy/GiNZA で人名・組織名を検出して伏字化(オプション):

- 業務文脈では「課長」「○○課」など固有名詞も意味を持つので、伏字化しすぎると要約品質が落ちる
- 推奨: 個人名のうち「マスク辞書に明示登録されたもの以外」を伏字化、組織・役職は残す
- **許可リスト方式**: 浦安市・市民スポーツ課・既知関係先・家族はマスクしない
- 自分(遠藤)の発言は伏字化しない

マスク辞書: `pii_dict.yaml` を Vault 外で管理し運用しながら拡充。

#### 4.3.6 ⑤ Claude API 構造化プロンプト

`_プロンプト/claude-structuring.md` 参照(Vault テンプレに同梱)。要点:

- 1つの録音から **複数のコンテキスト**を抽出可能(電話中に話題が転換した場合など)
- 各コンテキストに対して:
  - 要約(3-5文)
  - ToDo(期限・担当付き)
  - 人物(自動的に `[[人物名]]` リンクに)
  - トピック(同上)
  - 場所(同上)
  - **領域タグ(複数可)**: `業務`, `私的`, `知的興味`, `家族`, `健康`, `趣味`, `投資` など
  - **重要度スコア**: 1-5
  - 感情温度: ポジティブ / ニュートラル / ネガティブ / 葛藤
- **雑談・テスト録音は出力に含めない**(空配列で返す)
- 不確実な情報は `(要確認)` と付記

#### 4.3.7 ⑥ Obsidian Vault 出力

§5 で詳述。要点:

- 録音1件 → `録音/YYYY-MM-DD/HH-MM-SS.md` 1ノート生成
- 同日の `日次/YYYY-MM-DD.md` に追記(リンク + 要約スニペット)
- 抽出された `[[人物]]` `[[トピック]]` `[[場所]]` ノートが存在しなければ skeleton を自動生成
- `一覧/ToDo.md` `一覧/重要度高.md` を再生成(全 Vault スキャン)

-----

## 5. Obsidian Vault 設計

### 5.1 フォルダ構造

```
音声記憶/                         ← Vault ルート
├── .obsidian/                   ← Obsidian 設定(初回起動で自動生成)
├── 録音/
│   └── YYYY-MM-DD/
│       └── HH-MM-SS.md          ← 1録音 = 1ノート
├── 日次/
│   └── YYYY-MM-DD.md            ← その日の全録音への [[]] 集約
├── 人物/
│   └── 田中さん.md               ← 自動抽出・累積される人物ノート
├── トピック/
│   └── モルック大会.md           ← 案件・テーマの軸ノート
├── 場所/
│   └── 総合体育館.md
├── 一覧/
│   ├── ToDo.md                  ← 全未完了 ToDo の横串
│   └── 重要度高.md               ← 重要度 4-5 の録音一覧
├── _テンプレート/                ← ノート手動作成時の雛形
│   ├── 録音ノート.md
│   ├── 日次ノート.md
│   ├── 人物ノート.md
│   └── トピックノート.md
├── _プロンプト/                  ← パイプラインが参照
│   ├── claude-structuring.md
│   └── whisper-initial-prompt.txt
└── _生成ログ/
    └── YYYY-MM-DD.log           ← パイプライン処理の生ログ
```

`_` で始まるフォルダはパイプライン・テンプレ用、それ以外はユーザーが日常的に見るもの。

### 5.2 録音ノートのテンプレート

```markdown
---
date: 2026-05-23
time: 13:39:19
duration: 5m23s
audio_path: "../../Just Press Record/2026-05-23/13-39-19.m4a"
counterpart: ["[[田中さん]]"]
topics: ["[[モルック大会]]", "[[備品調達]]"]
locations: ["[[総合体育館]]"]
domains: [業務, 私的]
importance: 4
sentiment: ニュートラル
tags: [録音, 業務, 私的]
---

# 13:39 田中さんとの電話

## 要約
3-5文の要点...

## ToDo
- [ ] 来週までに見積もり確認 #todo
- [ ] 田中さんに資料送付 #todo

## キーポイント
- 合意事項のリスト
- 未解決の論点

## 全文(タイムスタンプ付き)
[00:00] こんにちは、田中です...
[00:12] ...

## 関連
- [[2026-05-22]] - 前日の打ち合わせ
- [[モルック大会]]
- [[田中さん]]

---
[原音を再生](../../Just%20Press%20Record/2026-05-23/13-39-19.m4a)
```

### 5.3 タグ規約

| タグ | 意味 |
|---|---|
| `#業務` | 仕事関連 |
| `#私的` | プライベート |
| `#知的興味` | 学習・思考メモ |
| `#家族` | 家族関連 |
| `#健康` | 体調・運動・医療 |
| `#趣味` | モルック・ゲーム等 |
| `#投資` | 資産・金銭判断 |
| `#要対応` | 期限付き ToDo を含む |
| `#重要` | 重要度 4-5 自動付与 |
| `#要確認` | 文字起こし精度疑い |

複数付与可。Claude API のプロンプトで「単一に分類せず、該当するもの全部付与」と指示。

### 5.4 リンク戦略

- **人物**: `[[人物/田中さん]]` または `[[田中さん]]`(Obsidian は自動解決)
- **トピック**: 案件・テーマ名で `[[]]`(同義語は人物ノート側で別名管理)
- **場所**: 施設名・地名で `[[]]`
- **日付**: `[[2026-05-23]]` で日次ノートにリンク
- **音声本体**: `../../Just Press Record/2026-05-23/13-39-19.m4a` を相対パスで(Obsidian は Vault 外ファイルも開ける)

### 5.5 グラフビュー活用

Obsidian のグラフビューで:

- 業務トピックと私的トピックの交差点が見える
- 人物ノードのクラスタリングで「誰と何の話をよくしてるか」が浮かぶ
- 孤立ノード = 1度きりの話題、ハブノード = 継続案件

-----

## 6. フェーズ計画

| Phase | 内容 | 完了条件 | 想定工数 | 状態 |
|---|---|---|---|---|
| **1** | Just Press Record 設定 + iCloud for Windows + 軽フィルタ + WhisperX 文字起こし | Watch で録音 → 数分後に ThinkPad のテキストファイル(生文字起こし)生成 | 半日 | ✅ 実装済 |
| **2** | Obsidian Vault 作成 + Claude API 構造化(基本) | 録音ノート1件が Vault に生成、リンクは未自動 | 半日 | ✅ 実装済 |
| **3** | エンティティ抽出 + 自動リンク + 日次ノート集約 | グラフビューに人物・トピックノードが現れる | 1日 | ✅ 実装済 |
| **4** | PII マスキング層追加 + 領域タグ + 重要度スコア | マスク後に Claude API、複数タグ付与 | 1日 | ✅ 実装済(regex + ユーザー辞書。GiNZA NER は Phase 5+) |
| **5** | Watch 話者分離(WhisperX diarization)+ Reminders 連携 + エラー UI | 期限付き ToDo が Apple Reminders に、失敗ファイル再実行可 | 余裕がある時 | 未着手 |

**Phase 1+2 で MVP。** 「ペタペタ貼る」運用はここで卒業。Phase 3 で Obsidian の真価が出る(`人物/`・`トピック/`・`場所/` の skeleton 自動生成、`日次/YYYY-MM-DD.md` 集約、`一覧/ToDo.md`・`一覧/重要度高.md` 自動再生成)。

-----

## 7. 設定値・環境変数

`.env`:

```
# iCloud Drive パス(ThinkPad での同期先)
JPR_INBOX_PATH=C:\Users\xxx\iCloud Drive\Just Press Record
VAULT_PATH=C:\Users\xxx\iCloud Drive\音声記憶

# 軽フィルタ
SKIP_DURATION_THRESHOLD_S=10
SKIP_SILENCE_RATIO=0.95

# WhisperX
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
DIARIZE_ENABLED=false
HF_TOKEN=hf_xxxxxxxxxxxxxxxx           # Phase 5 で必要

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-opus-4-7

# PII マスキング
PII_DICT_PATH=./pii_dict.yaml
PII_ALLOWLIST_PATH=./pii_allowlist.yaml
```

-----

## 8. コスト試算(月額)

| 項目 | 金額 | 備考 |
|---|---|---|
| Just Press Record | ¥0(初回 $4.99 のみ) | サブスクなし |
| iCloud (50GB以上を想定) | ¥130〜 | 既存契約があれば追加なし |
| WhisperX (ローカル) | ¥0 | |
| Anthropic Claude API | ¥500〜2,000 | 構造化要約のみ、件数次第 |
| Obsidian | ¥0 | 個人利用は無料 |
| **合計増分** | **約 ¥500〜2,000** | |

-----

## 9. オープン論点(実装中に判断)

- [ ] Watch 録音のサンプリングレート / モノラル品質が Whisper 精度に与える影響を初週で実測
- [ ] 軽フィルタの閾値(10秒・無音95%)は実データで調整
- [ ] PII マスキングで家族名を伏字化するか → 自分は伏字化しない、家族は要検討
- [ ] Claude プロンプトでの「業務/私的/知的興味」の境界定義
- [ ] 重要度スコアのキャリブレーション(主観と Claude の評価のズレ確認)
- [ ] 既存ボイスメモパイプライン(短尺・GAS経由)との関係
- [ ] 1日の終わりに「本日のまとめ」を Slack/メール通知するか
- [ ] バックログ(過去の文字起こし)の一括取込みUI
- [ ] Vault の Git バージョン管理(プライベートリポジトリ)有無
- [ ] Obsidian モバイル($8/月)で iPhone でも編集するか、閲覧は Files アプリの Markdown プレビューで足りるか

-----

## 10. リスクと緩和策

| リスク | 緩和策 |
|---|---|
| ThinkPad が長期間オフ → 録音が溜まる | iCloud に貯まり続けるだけ。起動時に順次処理 |
| **Watch → iPhone 同期遅延 / iCloud アップロード遅延** | 録音から ThinkPad 到着まで数十秒〜数十分の遅延を前提に運用 |
| **Watch 画面ロックで録音停止** | 「常にオン」モード、または長尺は iPhone で |
| **Just Press Record の仕様変更 / 開発停止** | 録音は標準 .m4a。代替: VoxRec / RecorderHQ。データ自体は iCloud に残る |
| **iCloud for Windows の同期不調** | 同期ステータス監視。手動で iCloud アプリの「再同期」 |
| **PII マスキング漏れ** | 段階的に正規表現と辞書を拡充、運用ログでチェック |
| **Claude API のJSON フォーマット崩れ** | パース失敗時は再試行 + raw 出力を `_失敗/` へ |
| **WhisperX の精度不足** | `initial_prompt` を業務用語+私的用語で充実 |
| **Vault が肥大化してグラフが見づらい** | 古い録音は年次でアーカイブフォルダへ。リンクは保持 |
| **業務/私的の混在で機微情報が見えやすい** | Vault 全体を BitLocker / FileVault で暗号化。Obsidian モバイル使う場合は端末ロック必須 |
| **Vault が iCloud で壊れる** | Git で別バックアップ。または週1で別ドライブにコピー |

-----

## 11. 採用アプリの選定理由(Just Press Record)

Apple Watch 単独録音アプリの候補と評価:

| アプリ | 評価 |
|---|---|
| **Just Press Record(採用)** | $4.99 買い切り。**iCloud Drive の通常フォルダに `.m4a` 保存** = Windows でも素直に同期可。Watch 単独録音◎、オンデバイス文字起こし、データ収集なし |
| 純正ボイスメモ | 無料。iCloud 同期は Apple デバイス間のみで **Windows からは一切アクセス不可**(private container)。Shortcut での自動エクスポートも Recording 型が File に変換できず実質不可 |
| VoxRec | 無料(AI有料)。Google Drive 直結◎だが、Google アカウントを介する分プライバシー観点で1段不利 |
| RecorderHQ | Google Drive 対応・Watch 対応。日本語精度の評判が見つけにくい |
| Whisper Memos | 録音→AI要約まで自動。**音声が OpenAI に送信される** → §2.1 に反するため不採用 |

将来 Just Press Record の仕様変更が発生した場合は VoxRec → RecorderHQ → 純正(Shortcut 修正) の順で代替検討。

-----

## 12. 補足: 純正ボイスメモを採用しなかった経緯

設計初期は VoxRec、その後「純正ボイスメモ + Shortcut で iCloud Drive に書き出す」案を検証したが、以下の理由で断念:

1. iOS Shortcuts の「録音を検索」アクションが返す `Recording` 型は **音声バイナリへの参照ではなくメタデータのみ**
2. `ファイルを保存` に渡すと 15バイトのスタブが書き出される
3. `メディアをエンコード` に渡すと「録音をメディアに変換できなかった」エラー
4. Apple の公式ドキュメントでも、ボイスメモの Files への書き出しは **手動の「共有 → ファイルに保存」のみ** が案内されている
5. 純正ボイスメモの iCloud 同期は Apple デバイス間のみ(private container 保存)、iCloud for Windows の同期対象外

→ 純正ボイスメモは **手動で書き出す運用なら使えるが、自動パイプラインの起点には不向き** と結論。

-----

以上。実装はこれをコンテキストとして Claude Code へ渡す前提。各 Phase 完了時にこの仕様書も更新していく。
