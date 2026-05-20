# 業務録音パイプライン セットアップ手順

> Apple Watch + VoxRec + Google Drive + ThinkPad で業務録音を自動処理するパイプラインのセットアップ手順。チェックボックス付きなので、進捗を追いながら進められます。

最終更新: 2026-05-20
関連: [`docs/voice-pipeline.md`](./voice-pipeline.md)(設計仕様書)

-----

## ⏱ 全体の所要時間と推奨順序

| フェーズ | 内容 | 所要時間 | やる場所 |
|---|---|---|---|
| **A** | iPhone / Apple Watch で録音 → Drive 到着確認 | 15分 | iPhone と Apple Watch |
| **B** | Google Drive のフォルダ整理 | 5分 | iPhone か PC |
| **C** | ThinkPad のセットアップ | 2〜3時間 | ThinkPad の前 |

**A → B → C の順で。** A で「録音が Drive に届く」が確認できないと、C で何やっても無駄なので、必ず A から。

-----

## A. iPhone と Apple Watch で録音 → Drive 到着まで確認

### A-1. VoxRec をインストール

- [ ] App Store で「**VoxRec**」を検索
- [ ] 「Voice to Text Dictation VoxRec」(開発元: DeepSine)をインストール
- [ ] アプリを開く
- [ ] マイクへのアクセスを許可
- [ ] (アプリが何か機能の説明をしてきたらスキップでOK)

### A-2. Google Drive と接続

- [ ] アプリ右下の **Settings(歯車アイコン)** をタップ
- [ ] **Cloud Sync** か **Backup** という項目を探してタップ
   - バージョンや表示言語で名称が違うことあり。「クラウド」「バックアップ」っぽい単語を探す
- [ ] クラウド先候補から **Google Drive** を選択
- [ ] **業務用の Google アカウント** でログイン
- [ ] アクセス許可を承認
- [ ] バックアップ先フォルダの選択画面が出る → ひとまず「ルート」のまま進む(B で正式なフォルダに変更する)
- [ ] **Auto Backup を ON**(録音停止 → 自動アップロード)

### A-3. 🚨 自社AI機能を必ず OFF にする(必須)

これ忘れると音声が VoxRec のサーバに送られて、業務 PII 的にアウト。

- [ ] Settings の中で **Transcription / Live Dictation / Speech to Text** という項目を探す
- [ ] **すべて OFF にする**
- [ ] 確認スクショを iPhone に保存しておく(あとで設定が変わってないか見返せるように)
- [ ] 録音時に「Live Transcribe」ボタンが出ても押さない、と覚えておく

### A-4. Apple Watch にコンプリケーションを置く

- [ ] iPhone の **「Watch」アプリ**(Apple純正の設定アプリ)を開く
- [ ] **「文字盤ギャラリー」** または現在の文字盤の編集画面へ
- [ ] コンプリケーションの空きスロットに **VoxRec** を追加
- [ ] Apple Watch の文字盤を見て、VoxRec のアイコンが出ていることを確認

### A-5. 試し録音

- [ ] Apple Watch の文字盤の VoxRec アイコンをタップ → 録音開始
- [ ] 「テスト録音です、これは1回目」と10秒くらい話す
- [ ] もう一度タップして停止
- [ ] iPhone を開いて VoxRec アプリで録音一覧に出ているか確認
- [ ] iPhone で **Google Drive アプリ** を開いて、m4a ファイルが届いているか確認(数十秒〜数分の遅延あり)

✅ **届いたら A は成功。これがパイプラインの根幹。届かない場合は[トラブルシュート](#トラブルシュート)へ。**

-----

## B. Google Drive のフォルダ整理

A-2 でルートにバックアップしてしまったので、ちゃんとしたフォルダ構造を作ってバックアップ先を変更します。

### B-1. フォルダを作る

- [ ] iPhone か PC で Google Drive を開く(`drive.google.com` でも、Driveアプリでも可)
- [ ] マイドライブ直下に **`ボイス録音`** フォルダを作成
- [ ] `ボイス録音` の中に以下の4つのサブフォルダを作成:
  - [ ] `inbox`(未処理ファイル置き場)
  - [ ] `processed`(処理済みファイル置き場)
  - [ ] `skipped`(短すぎる・無音ファイル)
  - [ ] `failed`(エラーで処理できなかったファイル)
- [ ] マイドライブ直下に **`業務記録`** フォルダを作成(Markdown 日次まとめが入る)

### B-2. VoxRec のバックアップ先を inbox に変更

- [ ] VoxRec を開いて Settings → Cloud Sync(またはBackup)
- [ ] バックアップ先フォルダを **`ボイス録音/inbox`** に変更
- [ ] もう一度試し録音(10秒程度)
- [ ] Drive の `ボイス録音/inbox` に届くか確認

✅ **inbox に届いたら B も成功。**

-----

## C. ThinkPad のセットアップ(後日 OK)

ここから先は ThinkPad の前に座らないとできない作業です。**A・B が動いてから着手**してください。

詳細な手順は項目ごとに別途案内します(WhisperX のインストール、Google Cloud Console でのサービスアカウント作成などは詰まりやすいポイントが多い)。ここではざっくりのやることリストだけ。

- [ ] Python 3.11 以上をインストール
- [ ] WhisperX をインストール
- [ ] FFmpeg をインストール(WhisperX の前提)
- [ ] Google Cloud Console でサービスアカウント作成、JSONキーを ThinkPad に保存
- [ ] Drive と Sheets を作成したサービスアカウントに共有
- [ ] Anthropic の API キー取得(Claude を呼ぶための鍵)
- [ ] プロジェクトフォルダ作成:`~/projects/voice-pipeline/`
- [ ] `.env` ファイルにキーや設定値を書く
- [ ] Phase 1 スクリプトを書く(`pipeline/phase1_transcribe.py`)
- [ ] テスト用音声で end-to-end 動作確認
- [ ] watchdog 常駐 or タスクスケジューラに登録

**この段階に来たら、項目ごとに「次これやりたい、手順教えて」と聞いてください。** 例:「Python 入れる手順教えて」「Google Cloud Console でサービスアカウント作る手順教えて」など。

-----

## トラブルシュート

### A-5 で Drive に届かない

考えられる原因(上から順に確認):

1. **iPhone と Watch が連動してない** → iPhone の Watch アプリで Watch がペアリングされているか確認
2. **iPhone がオフライン / 機内モード** → Wi-Fi または モバイル通信が ON か確認
3. **VoxRec の Auto Backup が OFF** → Settings で再確認
4. **Google Drive の認証が切れている** → Settings → Cloud Sync で再認証
5. **Google アカウントの容量不足** → Drive を開いて空き容量を確認

それでも届かない場合は、**iPhone の VoxRec アプリ内で手動アップロード**を試して、エラーメッセージを確認 → スクショ送ってください。

### A-3 で「Live Transcribe を有効にしますか」と聞かれる

- 「いいえ」「Skip」「あとで」を選んでください
- 間違って「はい」にしてしまった場合は、すぐ Settings でその機能を OFF に戻す

### VoxRec の画面表記が違う

- バージョンや言語設定で名称が違うことあり(「Settings」が「設定」、「Cloud Sync」が「クラウド同期」など)
- 私が書いた単語と完全一致しなくても、似た意味のものを選んでください
- どうしても見つからない場合はスクショ送ってください

### サブスクリプションを勧める画面が出る

- VoxRec の有料版は AI 文字起こし機能を使うためのもの
- このパイプラインでは **AI 文字起こしは使わない** ので **無料のままで OK**
- 「Continue with Free」「あとで」を選んでください

-----

## ⚠️ 守るべきこと

1. **VoxRec の自社AI機能は絶対に ON にしない**(A-3)
2. **業務用 Google アカウント**を使う(個人と混ぜない)
3. **最初の1週間は録音のたびに Drive に届いたか目視確認**(慣れるまでは保険)
4. **VoxRec のサブスク誘導画面に流されない**(Free のままで全機能足りる)
