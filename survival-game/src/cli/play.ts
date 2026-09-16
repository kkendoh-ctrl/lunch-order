/**
 * ターミナルで遊ぶための入口。
 *   npm run play            … 乱数の種は毎回ランダム
 *   npm run play -- --seed 7 … 種を固定（同じ選択なら同じ結果になる）
 *
 * 表示と入力だけを担当し、ゲームのルールは src/model に任せる。
 */
import * as readline from 'node:readline';
import { stdin, stdout } from 'node:process';
import { createInitialState } from '../model/data.ts';
import { advanceDay, judgeOutcome } from '../model/simulation.ts';
import { createRng } from '../model/rng.ts';
import type { Action, DayPlan, RationLevel } from '../model/types.ts';
import { formatOutcome, formatStatus } from './format.ts';

function parseSeed(argv: string[]): number {
  const i = argv.indexOf('--seed');
  if (i >= 0 && argv[i + 1]) return Number(argv[i + 1]);
  return Math.floor(Math.random() * 1_000_000);
}

async function main(): Promise<void> {
  const seed = parseSeed(process.argv);
  const rng = createRng(seed);
  const readLine = createLineReader();

  // 入力を「候補のどれか」に揃えるための小道具。空Enter（または入力終了）なら既定値
  const ask = async <T extends string>(question: string, choices: Record<string, T>, def: T): Promise<T> => {
    for (;;) {
      stdout.write(question);
      const raw = (await readLine())?.trim().toLowerCase();
      if (raw === undefined) {
        stdout.write('\n');
        return def;
      }
      if (raw === '') return def;
      if (raw in choices) return choices[raw]!;
      console.log('  → 選択肢の文字を入力してください');
    }
  };

  console.log('災害サバイバル・シミュレーション（試作）  seed=' + seed);
  console.log('大地震で街区が孤立した。救助は5日目に来るという。');
  console.log('');

  let state = createInitialState();
  while (!state.finished) {
    console.log(formatStatus(state));
    console.log('');

    const actions: Record<string, Action> = {};
    for (const s of state.survivors.filter((s) => s.status === 'alive')) {
      actions[s.id] = await ask(
        `  ${s.name}の行動  [t]探索 / [r]休息 (既定:r) > `,
        { t: 'explore', r: 'rest' },
        'rest',
      );
    }
    const rationChoices: Record<string, RationLevel> = { f: 'full', h: 'half', n: 'none' };
    const waterRation = await ask('  水の配給  [f]全員1人分 / [h]半分 / [n]なし (既定:f) > ', rationChoices, 'full');
    const foodRation = await ask('  食料の配給 [f]全員1人分 / [h]半分 / [n]なし (既定:f) > ', rationChoices, 'full');

    const plan: DayPlan = { actions, waterRation, foodRation };
    state = advanceDay(state, plan, rng);

    console.log('');
    for (const line of state.log) console.log(line);
    console.log('');
  }

  console.log(formatStatus(state));
  console.log('');
  console.log(formatOutcome(judgeOutcome(state)));
  process.exit(0);
}

/**
 * 1行ずつ読む関数を作る。
 * キーボード入力でも、パイプで流し込んだ入力（テストや自動実行）でも同じように動くよう、
 * 届いた行をいったん配列に貯めておき、求められたときに1行ずつ渡す。
 * 入力が終わっていて行が無ければ undefined を返す。
 */
function createLineReader(): () => Promise<string | undefined> {
  const rl = readline.createInterface({ input: stdin, terminal: stdin.isTTY ?? false });
  const buffered: string[] = [];
  const waiting: Array<(line: string | undefined) => void> = [];
  let closed = false;
  rl.on('line', (line) => {
    const w = waiting.shift();
    if (w) w(line);
    else buffered.push(line);
  });
  rl.on('close', () => {
    closed = true;
    for (const w of waiting.splice(0)) w(undefined);
  });
  return () =>
    new Promise((resolve) => {
      if (buffered.length > 0) resolve(buffered.shift());
      else if (closed) resolve(undefined);
      else waiting.push(resolve);
    });
}

main();
