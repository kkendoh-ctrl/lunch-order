import { Link } from 'react-router-dom'
import { Avatar } from './Avatar'
import { dexNo } from './DexCard'
import { regionById } from '../constants/prefectures'
import type { PlayerWithTeam } from '../types/database'

/** 地方一覧の2列グリッド用。 */
export function PlayerGridCard({ player }: { player: PlayerWithTeam }) {
  const accent = regionById(player.region_id)?.accent ?? '#83857a'
  return (
    <Link
      to={`/card/${player.id}`}
      className="group block overflow-hidden rounded-xl bg-white shadow-card transition active:scale-[.98] dark:bg-ink-900"
      style={{ borderTop: `3px solid ${accent}` }}
    >
      <div className="relative aspect-square overflow-hidden">
        <Avatar src={player.avatar_url} name={player.nickname} accent={accent} />
        {player.is_legend && (
          <span
            className="absolute left-2 top-2 rounded px-1.5 py-0.5 text-[10px] font-bold tracking-widest text-ink-950"
            style={{ backgroundColor: accent }}
          >
            伝説
          </span>
        )}
        {player.claim_status === 'unclaimed' && (
          <span className="absolute right-2 top-2 rounded bg-ink-900/70 px-1.5 py-0.5 text-[10px] tracking-widest text-ink-100">
            未確認
          </span>
        )}
      </div>
      <div className="p-2.5">
        <p className="font-mono text-[10px] tracking-widest" style={{ color: accent }}>
          {dexNo(player.dex_number)}
        </p>
        <p className="truncate text-sm font-medium text-ink-900 dark:text-ink-50">
          {player.nickname}
        </p>
        <p className="truncate text-[11px] text-ink-400 dark:text-ink-500">
          {player.teams?.name ?? player.prefecture}
        </p>
      </div>
    </Link>
  )
}
