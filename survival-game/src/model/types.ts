/**
 * ゲームの「状態」を表す型だけを集めたファイル。
 * ここにはロジック（計算）を書かない。型＝データの形の宣言。
 *
 * エンジン非依存にするため、このフォルダ(src/model)は
 * ブラウザにもNodeにもGodot向け変換にも依存しない純粋なTypeScriptで書く。
 */

/** 生存者の状態。alive=生存中 / dead=死亡 / left=集団を離脱（救助対象から外れる） */
export type SurvivorStatus = 'alive' | 'dead' | 'left';

export interface Survivor {
  /** プログラム内での識別子（表示には使わない） */
  id: string;
  name: string;
  age: number;
  /** 立ち絵やテキストで使う肩書き */
  role: string;
  /** 体力 0〜100。0で死亡 */
  hp: number;
  /** 空腹 0〜100。0=満腹、100=飢餓。高いほど体力と精神を削る */
  hunger: number;
  /** 精神 0〜100。0で離脱（一人で街へ出て行ってしまう） */
  morale: number;
  /** 探索の得意さ。1.0が標準。若くて体力のある人は高い */
  searchSkill: number;
  status: SurvivorStatus;
}

export interface Resources {
  /** 水（単位：人・日分。1で一人が一日分） */
  water: number;
  /** 食料（同上） */
  food: number;
}

/** 1人の生存者に対して、その日に指示する行動 */
export type Action = 'explore' | 'rest';

/** 配給の量。full=一人1単位 / half=一人0.5単位 / none=配らない */
export type RationLevel = 'full' | 'half' | 'none';

/** プレイヤーが1日に決める内容のまとめ */
export interface DayPlan {
  /** 生存者id → 行動 */
  actions: Record<string, Action>;
  waterRation: RationLevel;
  foodRation: RationLevel;
}

export interface GameState {
  /** 現在の日数。1から始まる */
  day: number;
  survivors: Survivor[];
  resources: Resources;
  /** その日に起きたことの文章ログ（UIがそのまま表示する） */
  log: string[];
  /** 救助判定が済んだら true。以後は進行しない */
  finished: boolean;
}

/** ゲーム終了時の結果 */
export interface Outcome {
  rescued: Survivor[];
  dead: Survivor[];
  left: Survivor[];
}
