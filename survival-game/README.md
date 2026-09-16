# 災害サバイバル・シミュレーション（試作）

大規模災害で孤立した街区に取り残された3人を、救助が来る5日目まで管理して生き延びさせる
2Dサバイバル・シミュレーションの**モデル部分の最小版**。舞台は浦安をモデルにした埋立地の街。

## 動かす

Node.js 22.18 以上が必要（TypeScript をそのまま実行できるため、ビルド工程がない）。

```bash
cd survival-game
npm install          # 型チェック用の typescript だけ入る
npm run play         # ターミナルで遊ぶ
npm run play -- --seed 7   # 乱数の種を固定（同じ選択なら同じ結果）
npm run compare      # 5つの固定戦略を2000回ずつ走らせ、救助人数の分布を比べる
npm test             # モデルのテスト
npm run typecheck    # 型チェック
```

## フォルダ構成

```
survival-game/
├── docs/design.md        設計表（変数・処理順・検証結果・次の候補）
└── src/
    ├── model/            ★ ゲーム本体。エンジン非依存の純粋なTypeScript
    │   ├── types.ts      状態の「形」だけ（生存者・資源・1日の計画）
    │   ├── data.ts       初期値と調整用の数字（バランスはここを触る）
    │   ├── rng.ts        種から再現できる乱数
    │   ├── simulation.ts 1日を進める advanceDay() と結果判定
    │   └── simulation.test.ts
    └── cli/              表示層（ターミナル版）。後で Web / Godot に置き換える
        ├── play.ts       対話プレイ
        ├── compare.ts    戦略比較
        └── format.ts     ステータスバーなどの整形
```

`src/model` は Node の機能（ファイル・端末）を一切使っていないので、
そのままブラウザ（React / Svelte）に持って行けるし、Godot 向けに書き直すときの仕様書にもなる。

## 現状の手応え

`docs/design.md` の第5節を参照。選択で結果は大きく変わる（0人〜2.79人）が、
「体力を見て交代で探索し、水を切らさない」方針が強すぎるため、次はイベント分岐で揺らす予定。
