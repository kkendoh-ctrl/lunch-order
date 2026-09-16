/**
 * 「選択で結果が変わるか」を数で確かめるスクリプト。
 *   npm run compare
 *
 * いくつかの決まった戦略（毎日同じ方針で選ぶ）を、乱数の種を変えながら
 * たくさん走らせ、救助人数の分布を比べる。
 * 戦略ごとに結果がはっきり違えば、モデルに「選択の意味」がある。
 */
import { createInitialState } from '../model/data.ts';
import { advanceDay, judgeOutcome } from '../model/simulation.ts';
import { createRng } from '../model/rng.ts';
import type { Action, DayPlan, GameState, RationLevel } from '../model/types.ts';
import { padDisplay } from './format.ts';

/** 戦略 = 状態を見て、その日の計画を返す関数 */
type Strategy = (state: GameState) => DayPlan;

const everyone = (state: GameState, action: Action): Record<string, Action> =>
  Object.fromEntries(state.survivors.map((s) => [s.id, action]));

/** 在庫が人数分あるなら full、半分あるなら half、なければ none */
const rationByStock = (stock: number, heads: number): RationLevel =>
  stock >= heads ? 'full' : stock >= heads / 2 ? 'half' : 'none';

const strategies: Record<string, Strategy> = {
  'A 全員休息・毎日フル配給': (state) => ({
    actions: everyone(state, 'rest'),
    waterRation: 'full',
    foodRation: 'full',
  }),

  'B 拓也だけ毎日探索・フル配給': (state) => ({
    actions: { ...everyone(state, 'rest'), takuya: 'explore' },
    waterRation: 'full',
    foodRation: 'full',
  }),

  'C 全員毎日探索・フル配給': (state) => ({
    actions: everyone(state, 'explore'),
    waterRation: 'full',
    foodRation: 'full',
  }),

  'D 体力上位2人が探索・在庫に応じて配給': (state) => {
    const living = state.survivors.filter((s) => s.status === 'alive').sort((a, b) => b.hp - a.hp);
    const actions = everyone(state, 'rest');
    for (const s of living.slice(0, 2)) actions[s.id] = 'explore';
    return {
      actions,
      waterRation: rationByStock(state.resources.water, living.length),
      foodRation: rationByStock(state.resources.food, living.length),
    };
  },

  'E 体力50以上だけ探索・水フル・食料は在庫次第': (state) => {
    const living = state.survivors.filter((s) => s.status === 'alive');
    const actions = everyone(state, 'rest');
    for (const s of living) if (s.hp >= 50) actions[s.id] = 'explore';
    return {
      actions,
      waterRation: 'full',
      foodRation: rationByStock(state.resources.food, living.length),
    };
  },
};

function runOnce(strategy: Strategy, seed: number): number {
  const rng = createRng(seed);
  let state = createInitialState();
  while (!state.finished) state = advanceDay(state, strategy(state), rng);
  return judgeOutcome(state).rescued.length;
}

const TRIALS = 2000;
console.log(`各戦略を ${TRIALS} 回ずつ実行（乱数の種 1〜${TRIALS}）\n`);
console.log(padDisplay('戦略', 46) + ' 平均救助  0人   1人   2人   3人');
for (const [name, strategy] of Object.entries(strategies)) {
  const counts = [0, 0, 0, 0];
  let sum = 0;
  for (let seed = 1; seed <= TRIALS; seed++) {
    const n = runOnce(strategy, seed);
    counts[n]! += 1;
    sum += n;
  }
  const pct = (c: number): string => `${((c / TRIALS) * 100).toFixed(0)}%`.padStart(4);
  console.log(
    padDisplay(name, 46) +
      ` ${(sum / TRIALS).toFixed(2)}人   ${counts.map(pct).join('  ')}`,
  );
}
