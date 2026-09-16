/**
 * モデルのテスト。Node標準の test runner を使う（追加ライブラリ不要）。
 *   npm test
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createInitialState, RESCUE_DAY, RULES } from './data.ts';
import { advanceDay, judgeOutcome } from './simulation.ts';
import { createRng } from './rng.ts';
import type { DayPlan, GameState } from './types.ts';

const restAll = (state: GameState): DayPlan => ({
  actions: Object.fromEntries(state.survivors.map((s) => [s.id, 'rest'])),
  waterRation: 'full',
  foodRation: 'full',
});

test('同じ種・同じ選択なら結果は毎回同じ', () => {
  const run = (): GameState => {
    const rng = createRng(42);
    let s = createInitialState();
    while (!s.finished) s = advanceDay(s, { ...restAll(s), actions: { takuya: 'explore' } }, rng);
    return s;
  };
  assert.deepEqual(run(), run());
});

test('advanceDay は元の状態を書き換えない', () => {
  const before = createInitialState();
  const snapshot = structuredClone(before);
  advanceDay(before, restAll(before), createRng(1));
  assert.deepEqual(before, snapshot);
});

test('休息すると体力が回復する（水ありの場合）', () => {
  const state = createInitialState();
  const yoshiko = state.survivors.find((s) => s.id === 'yoshiko')!;
  yoshiko.hp = 50;
  const next = advanceDay(state, restAll(state), createRng(1));
  const after = next.survivors.find((s) => s.id === 'yoshiko')!;
  assert.equal(after.hp, 50 + RULES.restHpGain);
});

test('水を配らないと全員の体力が減る', () => {
  const state = createInitialState();
  const next = advanceDay(state, { ...restAll(state), waterRation: 'none' }, createRng(1));
  for (const s of state.survivors) {
    const after = next.survivors.find((x) => x.id === s.id)!;
    // 休息の +15（上限100）のあと、水なしの -20
    const rested = Math.min(100, s.hp + RULES.restHpGain);
    assert.equal(after.hp, rested + RULES.waterHpDelta.none);
  }
});

test('在庫が足りないと弱い人から配られ、貰えない人の精神が下がる', () => {
  const state = createInitialState();
  state.resources.food = 1; // 3人いるのに1人分
  const next = advanceDay(state, restAll(state), createRng(1));
  // 体力最低は誠(50) → 誠だけ貰える
  const makoto = next.survivors.find((s) => s.id === 'makoto')!;
  const takuya = next.survivors.find((s) => s.id === 'takuya')!;
  assert.equal(makoto.hunger, 20 + RULES.foodHungerDelta.full);
  assert.equal(takuya.hunger, 40 + RULES.foodHungerDelta.none);
  assert.ok(takuya.morale < 50, '貰えなかった拓也の精神が下がる');
  assert.equal(next.resources.food, 0);
});

test('体力0になると死亡し、以後は行動しない', () => {
  const state = createInitialState();
  const makoto = state.survivors.find((s) => s.id === 'makoto')!;
  makoto.hp = 5;
  state.resources.water = 0;
  const next = advanceDay(state, { ...restAll(state), waterRation: 'none' }, createRng(1));
  assert.equal(next.survivors.find((s) => s.id === 'makoto')!.status, 'dead');
  const after = advanceDay(next, restAll(next), createRng(2));
  assert.ok(!after.log.some((l) => l.startsWith('誠は')), '死亡した人のログが出ない');
});

test('RESCUE_DAY 日目の処理後に終了し、生存者が救助される', () => {
  const rng = createRng(3);
  let s = createInitialState();
  s.resources.water = 99;
  s.resources.food = 99;
  let days = 0;
  while (!s.finished) {
    s = advanceDay(s, restAll(s), rng);
    days++;
  }
  assert.equal(days, RESCUE_DAY);
  assert.equal(judgeOutcome(s).rescued.length, 3);
  // 終了後はそれ以上進まない
  assert.deepEqual(advanceDay(s, restAll(s), rng), s);
});
