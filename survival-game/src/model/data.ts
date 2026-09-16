/**
 * 初期データと調整用の数値（バランス係数）。
 * 「面白くない」と感じたら、まずここの数字を触る。ロジック(simulation.ts)は触らない。
 * 表形式の説明は docs/design.md にある。
 */
import type { GameState, Survivor } from './types.ts';

/** 救助が来る日。この日の処理が終わった時点で生きていれば救助される */
export const RESCUE_DAY = 5;

export const RULES = {
  /** 探索した人の体力消費 */
  exploreHpCost: 15,
  /** 探索で怪我をする確率（体力40未満だと倍） */
  injuryChance: 0.2,
  injuryHpLoss: 20,
  injuryMoraleLoss: 10,
  /** 休息の回復量 */
  restHpGain: 15,
  restMoraleGain: 5,
  /** 探索で1回に見つかる量の上限（0〜この値の乱数 × 得意さ × 体力係数） */
  findMax: 2.5,
  /** 探索の成果による精神の変化 */
  findMoraleGoodGain: 5,
  findMoraleNothingLoss: 5,
  /** 水の配給量ごとの体力変化（水は切れるとすぐ効く） */
  waterHpDelta: { full: 0, half: -10, none: -20 },
  /** 食料の配給量ごとの空腹変化（配らなくても1日で+25腹が減る） */
  foodHungerDelta: { full: -10, half: 8, none: 25 },
  /** 配給量に対する不満（精神の変化） */
  rationMoraleDelta: { full: 0, half: -5, none: -10 },
  /** 「配るつもりだったのに在庫が足りず貰えなかった」人の追加不満 */
  shortageMoraleLoss: 15,
  /** 空腹が高いときのペナルティ */
  hungerWarnThreshold: 70,
  hungerWarnHpLoss: 10,
  hungerWarnMoraleLoss: 5,
  hungerMaxHpLoss: 20,
  /** 精神が低いときに口論が起きる確率と、周囲への影響 */
  lowMoraleThreshold: 20,
  quarrelChance: 0.3,
  quarrelMoraleLoss: 10,
} as const;

/** 生存者の初期値 */
export function createInitialSurvivors(): Survivor[] {
  return [
    {
      id: 'yoshiko',
      name: '佳子',
      age: 47,
      role: '元看護師・主婦',
      hp: 70,
      hunger: 30,
      morale: 60,
      searchSkill: 1.0,
      status: 'alive',
    },
    {
      id: 'takuya',
      name: '拓也',
      age: 22,
      role: '大学生',
      hp: 90,
      hunger: 40,
      morale: 50,
      searchSkill: 1.3,
      status: 'alive',
    },
    {
      id: 'makoto',
      name: '誠',
      age: 68,
      role: '元自治会長',
      hp: 50,
      hunger: 20,
      morale: 70,
      searchSkill: 0.7,
      status: 'alive',
    },
  ];
}

/** ゲーム開始時の状態。水6・食料4 = 3人が1日フル配給すると翌日には足りない量 */
export function createInitialState(): GameState {
  return {
    day: 1,
    survivors: createInitialSurvivors(),
    resources: { water: 6, food: 4 },
    log: [],
    finished: false,
  };
}
