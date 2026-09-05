import { Avatar } from './Avatar'
import { StyleTagChip } from './StyleTagChip'
import { BadgeSlots } from './BadgeSlots'
import { regionById } from '../constants/prefectures'
import type { PlayerWithTeam } from '../types/database'

export function dexNo(n: number) {
  return `No.${String(n).padStart(4, '0')}`
}

/** カード詳細の1枚。共有画像は ShareCard.tsx が別に描く。 */
export function DexCard({
  player,
  showBadges = true,
}: {
  player: PlayerWithTeam
  showBadges?: boolean
}) {
  const region = regionById(player.region_id)
  const accent = region?.accent ?? '#83857a'

  return (
    <div
      className="relative overflow-hidden rounded-2xl bg-white p-5 shadow-card dark:bg-ink-900"
      style={{ borderTop: `4px solid ${accent}` }}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs tracking-[0.2em]" style={{ color: accent }}>
          {dexNo(player.dex_number)}
        </span>
        <span className="text-[11px] tracking-[0.3em] text-ink-400 dark:text-ink-500">
          {region?.name ?? '—'}
        </span>
      </div>

      <div className="mt-4 flex items-start gap-4">
        <div
          className="h-24 w-24 shrink-0 overflow-hidden rounded-xl"
          style={{ outline: `1px solid ${accent}44` }}
        >
          <Avatar src={player.avatar_url} name={player.nickname} accent={accent} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {player.is_legend && (
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-bold tracking-widest text-ink-950"
                style={{ backgroundColor: accent }}
              >
                伝説
              </span>
            )}
            {player.claim_status === 'unclaimed' && (
              <span className="rounded border border-ink-300 px-1.5 py-0.5 text-[10px] tracking-widest text-ink-500 dark:border-ink-600 dark:text-ink-400">
                未確認
              </span>
            )}
          </div>

          <h2 className="mt-1 truncate text-xl font-bold text-ink-900 dark:text-ink-50">
            {player.nickname}
          </h2>

          <dl className="mt-2 space-y-0.5 text-xs text-ink-500 dark:text-ink-300">
            <div className="flex gap-2">
              <dt className="shrink-0 text-ink-400 dark:text-ink-500">所属</dt>
              <dd className="truncate">{player.teams?.name ?? '無所属'}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="shrink-0 text-ink-400 dark:text-ink-500">拠点</dt>
              <dd className="truncate">
                {player.prefecture}
                {player.home_ground ? ` / ${player.home_ground}` : ''}
              </dd>
            </div>
          </dl>

          {player.style_tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {player.style_tags.map((t) => (
                <StyleTagChip key={t} tag={t} accent={accent} />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-5 space-y-3 border-t border-dashed border-ink-200 pt-4 text-sm dark:border-ink-700">
        <p className="font-mincho leading-relaxed text-ink-900 dark:text-ink-50">
          <span className="mr-2 align-middle text-[10px] tracking-widest text-ink-400 dark:text-ink-500">
            決め台詞
          </span>
          {player.win_phrase || (
            <span className="text-ink-300 dark:text-ink-600">（未記入）</span>
          )}
        </p>
        <p className="font-mincho leading-relaxed text-ink-900 dark:text-ink-50">
          <span className="mr-2 align-middle text-[10px] tracking-widest text-ink-400 dark:text-ink-500">
            鳴き声
          </span>
          {player.miss_cry || (
            <span className="text-ink-300 dark:text-ink-600">（未記入）</span>
          )}
        </p>
      </div>

      {showBadges && (
        <div className="mt-5 border-t border-dashed border-ink-200 pt-4 dark:border-ink-700">
          <BadgeSlots />
        </div>
      )}
    </div>
  )
}
