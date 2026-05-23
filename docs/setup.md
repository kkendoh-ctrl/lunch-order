# 音声記憶パイプライン セットアップ手順

> Apple Watch + Just Press Record + iCloud Drive + ThinkPad + Obsidian で「音声記憶」を自動構造化するパイプラインのセットアップ手順。チェックボックス付きなので、進捗を追いながら進められます。

最終更新: 2026-05-23
関連: [`docs/voice-pipeline.md`](./voice-pipeline.md)(設計仕様書)

-----

## 全体の所要時間と推奨順序

| フェーズ | 内容 | 所要時間 | やる場所 |
|---|---|---|---|
| **A** | iPhone / Apple Watch で Just Press Record 録音 → iCloud Drive 到着確認 | 20分 | iPhone と Apple Watch |
| **B** | ThinkPad に iCloud for Windows を入れて Just Press Record フォルダが同期されるか確認 | 20分 | ThinkPad |
| **C** | Obsidian Vault 「音声記憶」を作成 | 10分 | iPhone or ThinkPad |
| **D** | ThinkPad パイプライン構築(WhisperX + Claude API + Vault 出力) | 2〜3時間 | ThinkPad |

**A → B → C → D の順で。** A で「録音が iCloud に届く」が確認できないと B 以降が全部無駄になるので、必ず A から。

-----

## A. iPhone と Apple Watch で Just Press Record で録音 → iCloud Drive 到着確認

### A-1. Just Press Record をインストール

- [ ] App Store で「**Just Press Record**」を検索(開発元: Open Planet Software)
- [ ] **$4.99(買い切り)**を購入してインストール
- [ ] アプリを開く
- [ ] マイクへのアクセスを許可
- [ ] 音声認識へのアクセスを許可(オンデバイスで使うため許可してOK)

### A-2. iCloud Drive 保存を確認

- [ ] アプリ右上の **歯車アイコン(設定)** をタップ
- [ ] **Cloud Storage** または **iCloud** の項目で **iCloud Drive がON**になっていることを確認
- [ ] (任意)**Transcription** はOFFにする
  - ThinkPad 側で WhisperX を使うので、オンデバイス文字起こしは不要
  - ONのままでも害はないが、Watch の電池消費が減る

### A-3. Apple Watch のコンプリケーションに配置

- [ ] iPhone の **「Watch」アプリ**(Apple純正)を開く
- [ ] **「文字盤ギャラリー」** または現在の文字盤の編集画面へ
- [ ] コンプリケーションの空きスロットに **Just Press Record** を追加
- [ ] Apple Watch の文字盤を見て、Just Press Record のアイコンが出ていることを確認

### A-4. 試し録音

- [ ] Apple Watch の文字盤の Just Press Record アイコンをタップ → 録音開始
- [ ] 「テスト録音です、これは1回目」と10秒くらい話す
- [ ] もう一度タップして停止
- [ ] iPhone を開いて Just Press Record アプリで録音一覧に出ているか確認
- [ ] iPhone の **「ファイル」アプリ** を開く
- [ ] `iCloud Drive` → `Just Press Record` → `2026-MM-DD`(今日の日付フォルダ)→ `HH-MM-SS.m4a` が**数十秒〜数分後**に届くか確認
- [ ] ファイルサイズが **KB〜MB 単位**(15バイトとかではない)で、タップすると音声プレイヤーが開いて再生できる

✅ **届いたら A は成功。これがパイプラインの根幹。届かない場合は[トラブルシュート](#トラブルシュート)へ。**

### A-5. (推奨)Watch 録音の運用ルール

- [ ] Watch 設定 → 画面表示と明るさ → **「常にオン」**(Always On)を ON にする(画面ロックによる録音停止を防ぐ)
- [ ] 録音中は **Watch の別アプリを開かない**(キャンセルされる)
- [ ] 最初の1週間は録音のたびに iPhone の「ファイル」アプリで届いたか目視確認

-----

## B. ThinkPad に iCloud for Windows を入れる

### B-1. iCloud for Windows をインストール

- [ ] ThinkPad で Microsoft Store または [Apple 公式](https://support.apple.com/ja-jp/guide/icloud-windows/set-up-icloud-windows-icw0144825a5/icloud)から **iCloud for Windows** をダウンロード
- [ ] インストール
- [ ] iPhone と同じ Apple ID でサインイン
- [ ] 2ファクタ認証コードを iPhone から入力

### B-2. iCloud Drive 同期を ON

- [ ] iCloud for Windows のメイン画面で **「iCloud Drive」** にチェック
- [ ] 「**Sync this PC**」または「**Sync iCloud Drive files to File Explorer**」を ON
- [ ] 初回同期完了を待つ(数分〜数十分、ファイル数による)

### B-3. Just Press Record フォルダの確認

- [ ] Windows の **エクスプローラ**を開く
- [ ] サイドバーに **「iCloud Drive」** が現れていることを確認
- [ ] `iCloud Drive` → `Just Press Record` → 日付フォルダ → A-4 で録音した `.m4a` ファイルが見える
- [ ] ファイルを右クリック → 「ローカルのコピーをダウンロード」(または自動でダウンロードされている)
- [ ] Windows Media Player などで再生できることを確認

✅ **エクスプローラで .m4a が見えて再生できたら B も成功。**

### B-4. WSL2 から触る場合(任意・後の D で使う)

- [ ] WSL2 のターミナルを開く
- [ ] `ls "/mnt/c/Users/<ユーザー名>/iCloud Drive/Just Press Record/"` で日付フォルダが見える
- [ ] パスは Windows ユーザー名次第なので、`echo $USER` や explorer 経由で確認

-----

## C. Obsidian Vault 「音声記憶」を作成

### C-1. Obsidian をインストール(ThinkPad と iPhone)

- [ ] **ThinkPad**: [obsidian.md](https://obsidian.md) から Windows 版をダウンロード・インストール(無料)
- [ ] (任意)**iPhone**: App Store から「Obsidian - Notes & Files」をインストール
  - 閲覧だけなら iPhone の「ファイル」アプリで Markdown プレビューも可
  - 編集もしたい場合は Obsidian モバイル(無料・iCloud Drive Vault 対応)

### C-2. Vault を iCloud Drive に作成

- [ ] iPhone の「ファイル」アプリで `iCloud Drive` の直下に **「音声記憶」** フォルダを作成
  - もしくは Windows のエクスプローラから作成しても可
- [ ] ThinkPad で Obsidian を起動 → **「Open folder as vault」** で `C:\Users\xxx\iCloud Drive\音声記憶` を選択
- [ ] 「Trust author and enable plugins」を選択(自分の Vault なので OK)
- [ ] 空の Vault が開く → 初回起動で `.obsidian/` フォルダが自動生成される

### C-3. Vault テンプレを取り込む

このリポジトリの `docs/obsidian-vault-template/` の中身を `音声記憶/` 配下にコピーします。

- [ ] このリポジトリを clone(または ZIP ダウンロード)
- [ ] `docs/obsidian-vault-template/` の中身を **全部** `iCloud Drive/音声記憶/` にコピー
- [ ] Obsidian を再起動 → サイドバーに `録音/` `日次/` `人物/` `トピック/` `場所/` `一覧/` `_テンプレート/` `_プロンプト/` フォルダが見える

### C-4. (推奨)Obsidian の初期設定

- [ ] **設定** → **エディター** → 「タブインデント」を OFF(マークダウン互換性のため)
- [ ] **設定** → **テンプレート** → テンプレートフォルダを `_テンプレート` に設定
- [ ] **設定** → **コアプラグイン** で以下をON:
  - グラフビュー
  - バックリンク
  - テンプレート
  - デイリーノート
- [ ] **設定** → **デイリーノート** → フォルダを `日次` に、日付フォーマットを `YYYY-MM-DD` に

### C-5. (任意)iPhone でも Vault を開く

- [ ] iPhone の Obsidian アプリを開く
- [ ] 「Create new vault」ではなく **「Open folder as vault」**
- [ ] iCloud Drive → 音声記憶 を選択
- [ ] ThinkPad と同じ Vault が iPhone でも開ける(iCloud 経由で自動同期)

✅ **Obsidian で Vault が開けて、テンプレ構造が見えていれば C も成功。**

-----

## D. ThinkPad パイプライン(後日 OK)

ここから先は ThinkPad で Python を書いて常駐させる作業です。**A・B・C が動いてから着手**してください。

詳細な手順は項目ごとに別途案内します。ここではざっくりのやることリストだけ。

### D-1. 前提ツール

- [ ] Python 3.11 以上をインストール(WSL2 推奨)
- [ ] FFmpeg をインストール(WhisperX の前提)
- [ ] `uv` か `venv` で仮想環境を作る

### D-2. WhisperX セットアップ(Phase 1)

- [ ] `pip install whisperx`
- [ ] `large-v3` モデルを初回ダウンロード(~3GB)
- [ ] テスト音声で文字起こしできるか確認

### D-3. Anthropic API キー取得(Phase 2)

- [ ] [console.anthropic.com](https://console.anthropic.com) でアカウント作成
- [ ] API キーを発行 → `.env` に保存
- [ ] `pip install anthropic`

### D-4. パイプライン本体(Phase 1〜5 を順に)

- [ ] プロジェクトフォルダ作成: `~/projects/voice-memory/`
- [ ] `.env` 作成
- [ ] Phase 1: `pipeline/p1_transcribe.py`(watchdog + 軽フィルタ + WhisperX)
- [ ] Phase 2: `pipeline/p2_structure.py`(Claude API で構造化 + Vault 出力)
- [ ] Phase 3: `pipeline/p3_entities.py`(人物・トピック自動リンク + 日次集約)
- [ ] Phase 4: `pipeline/p4_pii_mask.py`(PII マスキング層)
- [ ] Phase 5: 話者分離 / Reminders 連携 / エラー再実行 UI

**この段階に来たら、項目ごとに「次これやりたい、手順教えて」と聞いてください。** 例:「WhisperX 入れる手順教えて」「Claude プロンプト書きたい」など。

-----

## トラブルシュート

### A-4 で iCloud Drive に届かない

考えられる原因(上から順に確認):

1. **iPhone と Watch が連動してない** → iPhone の Watch アプリで Watch がペアリングされているか確認
2. **iPhone がオフライン / 機内モード** → Wi-Fi または モバイル通信が ON か確認
3. **Just Press Record の iCloud 設定が OFF** → アプリ設定で再確認
4. **iCloud にサインインしてない / 容量不足** → iPhone 設定 → Apple ID → iCloud で確認
5. **同期が単に遅延してる** → 5分待つ。それでも来なければ Just Press Record アプリ内の「未同期」リストを確認

それでも届かない場合は、**Just Press Record の Help → Resend All** を試してエラーメッセージを確認 → スクショ送ってください。

### B-3 でエクスプローラに iCloud Drive が出ない

- [ ] iCloud for Windows を再起動
- [ ] Windows を再起動
- [ ] iCloud for Windows の設定で iCloud Drive のチェックを外して再 ON

### B で .m4a がダウンロードされない(クラウドアイコンのまま)

- [ ] エクスプローラで該当ファイルを右クリック → 「常にこのデバイスに保持」を選択
- [ ] または `iCloud Drive\Just Press Record\` フォルダごと右クリックで同じ操作

### C-2 で Vault フォルダが Obsidian から開けない

- [ ] フォルダ名に絵文字や特殊文字を入れない(`音声記憶` は OK)
- [ ] iCloud のダウンロードが完了するまで待つ
- [ ] Obsidian を管理者権限で再起動

-----

## 守るべきこと

1. **Just Press Record の `Just Press Record/` フォルダの中身を手で動かさない**(JPR が自動管理してる)
2. **Vault の `_` で始まるフォルダ(`_テンプレート` `_プロンプト` `_生成ログ`)を手で消さない**(パイプラインが参照)
3. **`.obsidian/` フォルダを手で編集しない**(Obsidian の設定壊れる)
4. **最初の1週間は録音のたびに ThinkPad 同期も目視確認**(慣れるまで保険)
5. **PII マスキング辞書(`pii_dict.yaml`)は Vault の外に置く**(Vault 自体を共有・公開する可能性に備える)
