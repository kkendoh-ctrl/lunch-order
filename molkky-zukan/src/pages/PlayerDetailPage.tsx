import { Link, useNavigate, useParams } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from '../lib/auth'
import { useClaimCard, usePlayer } from '../hooks/useZukan'
import { DexCard } from '../components/DexCard'
import { ShareCardButton } from '../components/ShareCardButton'
import { DeletionRequestButton, ReportButton } from '../components/CardActions'
import { Button, EmptyState, ErrorState, Loading } from '../components/ui'
import { MESSAGES } from '../constants/messages'

export function PlayerDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data: player, isLoading, error } = usePlayer(id)
  const claim = useClaimCard()
  const [claimError, setClaimError] = useState<string | null>(null)

  if (isLoading) return <Loading label={MESSAGES.loadingCards} />
  if (error) return <ErrorState error={error} />
  if (!player) return <EmptyState>そのカードは見つからない</EmptyState>

  const isMine = !!user && player.user_id === user.id

  async function onClaim() {
    if (!player) return
    if (!user) {
      navigate(`/login?next=/card/${player.id}`)
      return
    }
    setClaimError(null)
    try {
      await claim.mutateAsync(player.id)
      navigate('/me')
    } catch (e) {
      setClaimError(
        e instanceof Error ? e.message : 'このカードは本人確認できませんでした',
      )
    }
  }

  return (
    <div className="space-y-5">
      <DexCard player={player} />

      {player.claim_status === 'unclaimed' && (
        <div className="rounded-xl border border-dashed border-ink-300 p-4 dark:border-ink-700">
          <p className="font-mincho text-sm text-ink-700 dark:text-ink-200">
            このカードはまだ本人確認されていない。
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-ink-400 dark:text-ink-500">
            Xで公開されているプロフィールから作られた下書きです。編集できるのは、Xでログインして本人と一致した人だけです。
          </p>
          <Button onClick={onClaim} disabled={claim.isPending} className="mt-3 w-full">
            自分のカードですか？
          </Button>
          {claimError && (
            <p className="mt-2 text-center text-[11px] text-ink-500 dark:text-ink-400">
              {claimError}
            </p>
          )}
        </div>
      )}

      {isMine && (
        <Link to="/me" className="block">
          <Button variant="ghost" className="w-full">
            このカードを編集する
          </Button>
        </Link>
      )}

      <ShareCardButton player={player} />

      {(player.source_url || player.x_handle) && (
        <p className="text-[11px] text-ink-400 dark:text-ink-500">
          出典：
          <a
            href={player.source_url ?? `https://x.com/${player.x_handle}`}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2"
          >
            {player.x_handle ? `@${player.x_handle}` : 'Xの公開プロフィール'}
          </a>
        </p>
      )}

      <div className="flex justify-between border-t border-ink-100 pt-4 dark:border-ink-800">
        <ReportButton playerId={player.id} reporterId={user?.id ?? null} />
        <DeletionRequestButton
          playerId={player.id}
          isUnclaimed={player.claim_status === 'unclaimed'}
        />
      </div>
    </div>
  )
}
