import { Link } from 'react-router-dom'
import { useRegionStats } from '../hooks/useZukan'
import { REGIONS } from '../constants/prefectures'
import { ErrorState, Loading } from '../components/ui'
import { MESSAGES } from '../constants/messages'

export function ZukanTopPage() {
  const { data, isLoading, error } = useRegionStats()

  if (isLoading) return <Loading />
  if (error) return <ErrorState error={error} />

  const counts = new Map(
    (data ?? []).map((s) => [s.region_slug, s]),
  )
  const total = (data ?? []).reduce((n, s) => n + Number(s.player_count), 0)

  return (
    <div className="space-y-5">
      <div>
        <p className="font-mincho text-sm text-ink-500 dark:text-ink-400">
          これまでに {total} 人が記録されている。
        </p>
      </div>

      <ul className="space-y-2">
        {REGIONS.map((region) => {
          const stat = counts.get(region.slug)
          const count = Number(stat?.player_count ?? 0)
          const legends = Number(stat?.legend_count ?? 0)
          const found = count > 0

          return (
            <li key={region.slug}>
              <Link
                to={`/region/${region.slug}`}
                className="flex items-center justify-between rounded-xl bg-white px-4 py-4 shadow-card transition active:scale-[.99] dark:bg-ink-900"
                style={{ borderLeft: `4px solid ${found ? region.accent : 'transparent'}` }}
              >
                <span className="flex items-baseline gap-3">
                  <span
                    className="font-mono text-[11px] tracking-widest"
                    style={{ color: found ? region.accent : undefined }}
                  >
                    {String(region.displayOrder).padStart(2, '0')}
                  </span>
                  <span
                    className={
                      found
                        ? 'text-base font-bold'
                        : 'text-base font-bold text-ink-300 dark:text-ink-600'
                    }
                  >
                    {found ? region.name : '？？'}
                  </span>
                </span>

                <span className="text-right">
                  {found ? (
                    <>
                      <span className="text-sm tabular-nums text-ink-700 dark:text-ink-200">
                        {count}
                      </span>
                      <span className="ml-1 text-[11px] text-ink-400 dark:text-ink-500">
                        人
                      </span>
                      {legends > 0 && (
                        <span
                          className="ml-2 text-[10px] tracking-widest"
                          style={{ color: region.accent }}
                        >
                          伝説 {legends}
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="font-mincho text-xs text-ink-300 dark:text-ink-600">
                      {MESSAGES.undiscovered}
                    </span>
                  )}
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
