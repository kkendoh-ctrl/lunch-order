import { Link, useParams } from 'react-router-dom'
import { regionBySlug } from '../constants/prefectures'
import { useRegionPlayers } from '../hooks/useZukan'
import { PlayerGridCard } from '../components/PlayerGridCard'
import { EmptyState, ErrorState, Loading } from '../components/ui'
import { MESSAGES } from '../constants/messages'

export function RegionPage() {
  const { slug } = useParams()
  const region = slug ? regionBySlug(slug) : undefined
  const { data, isLoading, error } = useRegionPlayers(region?.id)

  if (!region) return <EmptyState>その地方は見つからない</EmptyState>
  if (isLoading) return <Loading label={MESSAGES.loadingCards} />
  if (error) return <ErrorState error={error} />

  const players = data ?? []
  const legends = players.filter((p) => p.is_legend)
  const rest = players.filter((p) => !p.is_legend)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold" style={{ color: region.accent }}>
            {region.name}
          </h1>
          <p className="text-[11px] text-ink-400 dark:text-ink-500">
            {players.length} 人が記録されている
          </p>
        </div>
        <Link
          to="/"
          className="text-[11px] text-ink-400 underline underline-offset-2 dark:text-ink-500"
        >
          地方を選び直す
        </Link>
      </div>

      {players.length === 0 && <EmptyState>{MESSAGES.empty}</EmptyState>}

      {legends.length > 0 && (
        <section className="space-y-2">
          <h2
            className="text-[11px] tracking-[0.3em]"
            style={{ color: region.accent }}
          >
            伝説
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {legends.map((p) => (
              <PlayerGridCard key={p.id} player={p} />
            ))}
          </div>
        </section>
      )}

      {rest.length > 0 && (
        <section className="space-y-2">
          {legends.length > 0 && (
            <h2 className="text-[11px] tracking-[0.3em] text-ink-400 dark:text-ink-500">
              記録
            </h2>
          )}
          <div className="grid grid-cols-2 gap-3">
            {rest.map((p) => (
              <PlayerGridCard key={p.id} player={p} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
