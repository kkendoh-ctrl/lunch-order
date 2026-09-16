/**
 * 乱数生成器（RNG = Random Number Generator）。
 *
 * Math.random() を直接使わず、「種（seed）」から同じ乱数列を再現できるものを使う。
 * 理由：
 *  - テストで結果を再現できる
 *  - 「同じ種でも選択を変えたら結果が変わる」ことを確かめられる（＝面白さの検証）
 *  - 将来リプレイ機能やデバッグに役立つ
 *
 * アルゴリズムは mulberry32。短くて十分にバラつく。
 */
export interface Rng {
  /** 0以上1未満の実数を返す（Math.random と同じ約束） */
  next(): number;
  /** min以上max以下の整数を返す */
  int(min: number, max: number): number;
  /** 確率 p (0〜1) で true */
  chance(p: number): boolean;
}

export function createRng(seed: number): Rng {
  let a = seed >>> 0; // 32bit符号なし整数に揃える
  const next = (): number => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    int: (min, max) => min + Math.floor(next() * (max - min + 1)),
    chance: (p) => next() < p,
  };
}
