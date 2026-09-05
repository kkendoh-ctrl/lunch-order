# 全国モルッカー図鑑

モルック競技者が自分のカードを登録し、地方ごとに図鑑として閲覧できる PWA。
モンスター図鑑風の遊び心ある世界観だが、既存作品の意匠は一切使っていない完全オリジナル。

**いまはフェーズ1**（カード登録・図鑑閲覧・共有画像・PWA）。
フェーズ2（門番とバッジ）とフェーズ3（今日やりたい）は機能フラグで隠してある。

## 技術スタック

| 層 | 使うもの |
| --- | --- |
| フロント | Vite + React + TypeScript |
| PWA | vite-plugin-pwa（ホーム画面追加・オフライン閲覧） |
| バックエンド | Supabase（Postgres / Auth / Storage / Realtime） |
| 状態管理 | React Query（Supabaseクライアント経由） |
| スタイル | Tailwind CSS（ダークモード対応） |
| ホスティング | Cloudflare Pages |

## セットアップ

### 1. 依存関係

```bash
cd molkky-zukan
npm install
```

### 2. Supabase プロジェクトを作る

1. <https://supabase.com> でプロジェクトを新規作成する（無料枠でよい）。
2. SQL Editor で、この順にマイグレーションを実行する。
   - `supabase/migrations/0001_init.sql` … regions / teams / players / reports / deletion_requests、RLS、Storage
   - `supabase/migrations/0002_phase2_phase3.sql` … gyms / badges / match_rooms / match_messages（フェーズ2・3のぶん。今すぐ流しても画面には出ない）
3. Authentication → Providers で **Twitter (X)** を有効にする。
   - X Developer Portal で OAuth 2.0 アプリを作り、Client ID / Secret を入れる。
   - Callback URL は Supabase の画面に表示されるもの（`https://<project>.supabase.co/auth/v1/callback`）を X 側に登録する。
   - メールログイン（Magic Link）は既定で有効。
4. Authentication → URL Configuration の **Site URL** に、開発なら `http://localhost:5173`、本番なら Cloudflare Pages のURLを入れる。
   Redirect URLs にも `http://localhost:5173/**` と本番URLの `/**` を足しておく。

### 3. 環境変数

`.env.example` をコピーして `.env.local` を作る。実キーは絶対にコミットしない。

```bash
cp .env.example .env.local
```

| 変数 | どこで使う | 取り方 |
| --- | --- | --- |
| `VITE_SUPABASE_URL` | ブラウザ | Supabase → Project Settings → API → Project URL |
| `VITE_SUPABASE_ANON_KEY` | ブラウザ | 同 → anon public |
| `VITE_FEATURE_BADGES` | ブラウザ | フェーズ2の画面を出すなら `true` |
| `VITE_FEATURE_MATCH` | ブラウザ | フェーズ3の画面を出すなら `true` |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | 手元のスクリプト | 同 → service_role（**公開厳禁**） |
| `X_BEARER_TOKEN` | 手元のスクリプト | X Developer Portal（Basic以上の有料プラン） |

### 4. 起動

```bash
npm run dev       # http://localhost:5173
npm run build     # 型チェック + 本番ビルド
npm run preview   # ビルド結果を確認（Service Worker はここで初めて効く）
```

### 5. ダミーデータ（5人分）

```bash
npm run seed
```

`.env.local` の `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` を読んで、
チーム2件と架空の選手5人（うち伝説1人）を未確認カードとして入れる。
何度実行しても重複しない。

**確認方法**: 図鑑トップを開いて、北海道・関東・中部・九州沖縄・四国に人数が付いていれば成功。

## 各ステップの確認方法

| やったこと | 1行での確認方法 |
| --- | --- |
| マイグレーション | Supabase の Table Editor に `players` があり、`regions` に8行入っている |
| 認証とマイカード登録 | `/onboarding` でXまたはメールでログインし、5ステップ進めて `/me` に自分のカードが出る |
| 図鑑トップ・地方一覧・カード詳細 | `/` の地方をタップ →2列グリッド →カードをタップして詳細が開く |
| 共有画像生成 | カード詳細の「カード画像をつくって共有」で、図鑑ナンバーと地方名が入ったPNGが出る |
| PWA | `npm run preview` を実機で開き、ホーム画面に追加 →機内モードで開いて図鑑が読める |

## デプロイ（Cloudflare Pages）

1. Cloudflare ダッシュボード → Workers & Pages → Create → Pages → Connect to Git でこのリポジトリを繋ぐ。
2. ビルド設定:
   - **Framework preset**: なし（None）
   - **Build command**: `npm run build`
   - **Build output directory**: `molkky-zukan/dist`
   - **Root directory**: `molkky-zukan`
3. Settings → Environment variables に `VITE_SUPABASE_URL`、`VITE_SUPABASE_ANON_KEY`、
   （必要なら）`VITE_FEATURE_BADGES` / `VITE_FEATURE_MATCH` を Production / Preview 双方に入れる。
   **service_role キーと X_BEARER_TOKEN はここに入れない**（ブラウザに渡す場所ではない）。
4. デプロイ後、Supabase の Site URL / Redirect URLs に本番URLを追加する。これを忘れるとXログインが戻ってこない。

SPAのルーティングは `public/_redirects`（`/*  /index.html  200`）で処理している。

## Xからの取り込みについて

`npm run import:x -- handles.txt` で、Xの公開プロフィールから「未確認カード」を作る。

- **X API v2 の Basic 以上（有料）が前提**。無料枠ではユーザー取得が実質できないので、まず費用を確認すること。
  `X_BEARER_TOKEN` が無ければスクリプトはその旨を出して止まる。取り込みが動かなくても図鑑本体は動く。
- 取り込むのは X で公開されている範囲（表示名・アイコン・自己紹介・所在地）だけ。DMや非公開情報は扱わない。
- 取得したデータの再配布・第三者提供はしない。図鑑の表示にだけ使う。
- `source_url` にプロフィールURLを必ず残し、カード詳細に出典として表示する。
- レート制限に当たったら `x-rate-limit-reset` まで待つ。100件ずつに分けて叩く。
- 所在地から都道府県を読み取れない人は取り込まない（誤った地方に載せないため）。
- 本人確認済み（`claimed`）のカードは、取り込み側から上書きしない。

## 運営が介在しない仕組み

| 場面 | どう自動で終わるか |
| --- | --- |
| 本人確認 | Xログインの `x_user_id` が一致したときだけ `claim_card` が通る。運営の承認は挟まない |
| 削除依頼 | `request_card_deletion` を呼んだ時点で、未確認カードは即 `visibility='hidden'`。本人確認済みなら持ち主本人のときだけ |
| 通報 | 同一対象に3件たまると、トリガーが `is_auto_hidden` を立てて自動で見えなくなる。`reports` は service_role 以外から読めない |
| 部屋の期限（フェーズ3） | 作成から12時間で `expires_at` を過ぎ、RLS の時点で見えなくなる。`close_expired_match_rooms()` を定期実行すると status も畳まれる |

伝説フラグ（`is_legend`）と門番の任命（`gyms`）だけは手動。Supabase ダッシュボードから付ける。

**割り切っている点**: 未確認カードの削除依頼は、誰からでも受け付けて即座に非公開にする。
運営の確認を挟まない代わりに、第三者が他人の未確認カードを隠せてしまう。
依頼は `deletion_requests` に残るので、取り違えがあれば service_role から `visibility` を戻せる。

## 設計メモ

- `players.id` は `auth.users` と直結していない。未確認カードには auth ユーザーが存在しないため、
  nullable な `user_id` で1:1に紐づけている（`claim_status` との整合は CHECK 制約で担保）。
- 図鑑ナンバー `dex_number` は全国通し番号。シーケンスで採番し、本人にも編集させない。
- 地方は都道府県からトリガーで自動導出する。クライアントに決めさせない。
  対応表は `src/constants/prefectures.ts` と `0001_init.sql` の `region_slug_for_prefecture` の2箇所にある。片方を直したら両方直すこと。
- `dex_number` / `is_legend` / `claim_status` / `user_id` / `x_*` は、更新トリガーが利用者の書き換えを弾く。
- カード画像は画面用（`DexCard`）と書き出し用（`ShareCard`）を分けている。書き出し用は明暗テーマの影響を受けないよう色を直接書いている。
- アイコンは `npm run icons` で生成する（`scripts/generate-icons.mjs`、外部ライブラリなし）。

## ディレクトリ

```
molkky-zukan/
├── public/              アイコン、_redirects
├── scripts/             アイコン生成、X取り込み
├── src/
│   ├── components/      カード・フォーム部品・ダイアログ
│   ├── constants/       都道府県↔地方、スタイルタグ、文言
│   ├── hooks/           React Query のクエリとミューテーション
│   ├── lib/             Supabaseクライアント、認証、テーマ、機能フラグ
│   ├── pages/           図鑑トップ／地方一覧／カード詳細／マイカード／ログイン／オンボーディング
│   └── types/           DBの型
└── supabase/
    ├── migrations/      スキーマとRLS
    └── seed/            ダミーデータ投入
```
