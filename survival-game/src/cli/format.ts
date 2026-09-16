/**
 * ターミナル表示のための整形関数。モデル(src/model)には依存されない「表示層」。
 */
import type { GameState, Outcome, Survivor } from '../model/types.ts';

/** 全角文字を幅2として、指定幅まで半角スペースで埋める */
export function padDisplay(text: string, width: number): string {
  let w = 0;
  for (const ch of text) w += ch.charCodeAt(0) > 0xff ? 2 : 1;
  return text + ' '.repeat(Math.max(0, width - w));
}

/** 0〜100 の値を ██████░░░░ のようなバーにする */
function bar(v: number): string {
  const filled = Math.round(v / 10);
  return '█'.repeat(filled) + '░'.repeat(10 - filled);
}

function statusLabel(s: Survivor): string {
  if (s.status === 'dead') return '（死亡）';
  if (s.status === 'left') return '（離脱）';
  return '';
}

export function formatStatus(state: GameState): string {
  const lines: string[] = [];
  lines.push(`【${state.day}日目】 在庫  水:${state.resources.water}  食料:${state.resources.food}`);
  for (const s of state.survivors) {
    const head = padDisplay(`${s.name}(${s.age}・${s.role})${statusLabel(s)}`, 30);
    if (s.status !== 'alive') {
      lines.push(`  ${head}`);
      continue;
    }
    lines.push(
      `  ${head} 体力 ${bar(s.hp)} ${String(s.hp).padStart(3)}` +
        `  空腹 ${bar(s.hunger)} ${String(s.hunger).padStart(3)}` +
        `  精神 ${bar(s.morale)} ${String(s.morale).padStart(3)}`,
    );
  }
  return lines.join('\n');
}

export function formatOutcome(o: Outcome): string {
  const names = (list: Survivor[]): string => (list.length ? list.map((s) => s.name).join('・') : 'なし');
  return [
    '════════ 結果 ════════',
    `救助された：${names(o.rescued)}`,
    `亡くなった：${names(o.dead)}`,
    `離脱した　：${names(o.left)}`,
    '',
    o.rescued.length === 3
      ? '全員でヘリに乗った。誰も欠けなかった。'
      : o.rescued.length === 0
        ? '救助隊が見つけたのは、誰もいない避難所だった。'
        : `${o.rescued.length}人が救助された。残された荷物が、いなくなった人の分だけ多い。`,
  ].join('\n');
}
