/**
 * シミュレーションの中核。1日を進める advanceDay() と、結果を出す judgeOutcome()。
 *
 * 設計方針：
 *  - 「入力（状態＋プレイヤーの選択＋乱数）→ 出力（新しい状態）」の純粋な関数にする。
 *    元の state は書き換えず、コピーを返す。UI側が「戻る」「比較する」を作りやすい。
 *  - 起きたことは全部 state.log に日本語で残す。UIはそれを表示するだけでよい。
 *
 * 1日の流れ（順番が結果に影響するので固定）：
 *   1. 行動フェーズ  … 探索 / 休息
 *   2. 配給フェーズ  … 水と食料を配る
 *   3. 状態判定      … 空腹・精神の悪化、口論、死亡・離脱
 *   4. 日付を進める。RESCUE_DAY の処理が終わったら救助
 */
import type { Action, DayPlan, GameState, Outcome, RationLevel, Survivor } from './types.ts';
import type { Rng } from './rng.ts';
import { RESCUE_DAY, RULES } from './data.ts';

/** 0〜100 に収める小道具 */
const clamp = (v: number): number => Math.max(0, Math.min(100, Math.round(v)));

const alive = (s: Survivor): boolean => s.status === 'alive';

export function advanceDay(prev: GameState, plan: DayPlan, rng: Rng): GameState {
  if (prev.finished) return prev;

  // 元の状態を壊さないよう丸ごとコピーしてから書き換える
  const state: GameState = structuredClone(prev);
  state.log = [`── ${state.day}日目 ──`];

  runActions(state, plan.actions, rng);
  runRation(state, plan.waterRation, plan.foodRation);
  runConditions(state, rng);

  if (state.day >= RESCUE_DAY) {
    state.finished = true;
    state.log.push('遠くからヘリの音。救助隊が到着した。');
  } else {
    state.day += 1;
  }
  return state;
}

/* ---------- 1. 行動フェーズ ---------- */

function runActions(state: GameState, actions: Record<string, Action>, rng: Rng): void {
  for (const s of state.survivors.filter(alive)) {
    const action = actions[s.id] ?? 'rest';
    if (action === 'explore') explore(state, s, rng);
    else rest(state, s);
  }
}

function explore(state: GameState, s: Survivor, rng: Rng): void {
  s.hp = clamp(s.hp - RULES.exploreHpCost);

  // 体力が低いと収穫も減る：hp100で1.0倍、hp50で0.75倍、hp0で0.5倍
  const hpFactor = 0.5 + s.hp / 200;
  const roll = (): number => Math.round(rng.next() * RULES.findMax * s.searchSkill * hpFactor);
  const water = roll();
  const food = roll();
  state.resources.water += water;
  state.resources.food += food;

  const parts: string[] = [];
  if (water > 0) parts.push(`水${water}`);
  if (food > 0) parts.push(`食料${food}`);
  if (parts.length > 0) {
    state.log.push(`${s.name}は街区を探索し、${parts.join('・')}を持ち帰った。`);
  } else {
    state.log.push(`${s.name}は探索に出たが、液状化で崩れた道に阻まれ何も見つけられなかった。`);
  }

  const total = water + food;
  if (total >= 2) s.morale = clamp(s.morale + RULES.findMoraleGoodGain);
  if (total === 0) s.morale = clamp(s.morale - RULES.findMoraleNothingLoss);

  const injuryChance = s.hp < 40 ? RULES.injuryChance * 2 : RULES.injuryChance;
  if (rng.chance(injuryChance)) {
    s.hp = clamp(s.hp - RULES.injuryHpLoss);
    s.morale = clamp(s.morale - RULES.injuryMoraleLoss);
    state.log.push(`${s.name}は帰り道でマンホールの隆起に足を取られ、怪我をした。`);
  }
}

function rest(state: GameState, s: Survivor): void {
  s.hp = clamp(s.hp + RULES.restHpGain);
  s.morale = clamp(s.morale + RULES.restMoraleGain);
  state.log.push(`${s.name}は避難所で休んだ。`);
}

/* ---------- 2. 配給フェーズ ---------- */

/** 配給量を数値に。fullは1人分、halfは半人分 */
const rationAmount = (level: RationLevel): number =>
  level === 'full' ? 1 : level === 'half' ? 0.5 : 0;

function runRation(state: GameState, waterLevel: RationLevel, foodLevel: RationLevel): void {
  // 弱っている人から順に配る（在庫不足のとき誰が貰えないかを決めるため）
  const order = state.survivors.filter(alive).sort((a, b) => a.hp - b.hp);

  const distribute = (
    kind: 'water' | 'food',
    level: RationLevel,
    apply: (s: Survivor, got: RationLevel) => void,
  ): void => {
    const label = kind === 'water' ? '水' : '食料';
    const want = rationAmount(level);
    const shortage: string[] = [];
    for (const s of order) {
      if (want > 0 && state.resources[kind] >= want) {
        state.resources[kind] -= want;
        apply(s, level);
      } else {
        apply(s, 'none');
        if (want > 0) {
          // 配るつもりだったのに在庫切れ → 不公平感
          s.morale = clamp(s.morale - RULES.shortageMoraleLoss);
          shortage.push(s.name);
        }
      }
    }
    if (level === 'none') state.log.push(`${label}は配給しなかった。`);
    else if (shortage.length > 0)
      state.log.push(`${label}が足りず、${shortage.join('・')}には配れなかった。`);
    else state.log.push(`${label}を${level === 'full' ? '全員に1人分' : '全員に半分ずつ'}配った。`);
  };

  distribute('water', waterLevel, (s, got) => {
    s.hp = clamp(s.hp + RULES.waterHpDelta[got]);
    s.morale = clamp(s.morale + RULES.rationMoraleDelta[got]);
  });
  distribute('food', foodLevel, (s, got) => {
    s.hunger = clamp(s.hunger + RULES.foodHungerDelta[got]);
    s.morale = clamp(s.morale + RULES.rationMoraleDelta[got]);
  });
}

/* ---------- 3. 状態判定 ---------- */

function runConditions(state: GameState, rng: Rng): void {
  const living = state.survivors.filter(alive);

  // 空腹のペナルティ
  for (const s of living) {
    if (s.hunger >= 100) {
      s.hp = clamp(s.hp - RULES.hungerMaxHpLoss);
      s.morale = clamp(s.morale - RULES.hungerWarnMoraleLoss);
      state.log.push(`${s.name}は飢えで動けなくなってきた。`);
    } else if (s.hunger >= RULES.hungerWarnThreshold) {
      s.hp = clamp(s.hp - RULES.hungerWarnHpLoss);
      s.morale = clamp(s.morale - RULES.hungerWarnMoraleLoss);
      state.log.push(`${s.name}は空腹で弱っている。`);
    }
  }

  // 精神が低い人が口論を起こし、周囲の精神も下がる
  for (const s of living) {
    if (s.morale <= RULES.lowMoraleThreshold && s.morale > 0 && rng.chance(RULES.quarrelChance)) {
      for (const other of living) {
        if (other !== s) other.morale = clamp(other.morale - RULES.quarrelMoraleLoss);
      }
      state.log.push(`${s.name}が「いつまでここにいるんだ」と声を荒げ、空気が重くなった。`);
    }
  }

  // 死亡・離脱の判定
  for (const s of living) {
    if (s.hp <= 0) {
      s.status = 'dead';
      state.log.push(`${s.name}は静かに息を引き取った。`);
    } else if (s.morale <= 0) {
      s.status = 'left';
      state.log.push(`${s.name}は「もう待てない」と言い残し、一人で冠水した道へ出て行った。`);
    }
  }
}

/* ---------- 4. 結果 ---------- */

export function judgeOutcome(state: GameState): Outcome {
  return {
    rescued: state.survivors.filter((s) => s.status === 'alive'),
    dead: state.survivors.filter((s) => s.status === 'dead'),
    left: state.survivors.filter((s) => s.status === 'left'),
  };
}
