import { useRef, useState } from 'react'
import { toPng } from 'html-to-image'
import { ShareCard } from './ShareCard'
import { Button } from './ui'
import { dexNo } from './DexCard'
import { regionById } from '../constants/prefectures'
import type { PlayerWithTeam } from '../types/database'

type State = 'idle' | 'working' | 'saved' | 'error'

export function ShareCardButton({ player }: { player: PlayerWithTeam }) {
  const cardRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<State>('idle')

  const region = regionById(player.region_id)
  const text = `${dexNo(player.dex_number)} ${player.nickname}（${region?.name ?? ''}）\n#全国モルッカー図鑑`

  async function share() {
    if (!cardRef.current) return
    setState('working')
    try {
      const dataUrl = await toPng(cardRef.current, {
        pixelRatio: 2,
        backgroundColor: '#ffffff',
        cacheBust: true,
      })
      const blob = await (await fetch(dataUrl)).blob()
      const file = new File([blob], `molkky-${player.dex_number}.png`, {
        type: 'image/png',
      })

      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], text })
        setState('idle')
        return
      }

      // 共有に対応していない環境では、画像を保存してから投稿画面を開く。
      const a = document.createElement('a')
      a.href = dataUrl
      a.download = file.name
      a.click()
      window.open(
        `https://x.com/intent/post?text=${encodeURIComponent(text)}`,
        '_blank',
        'noopener',
      )
      setState('saved')
    } catch (e) {
      console.error(e)
      setState('error')
    }
  }

  return (
    <div>
      <Button onClick={share} disabled={state === 'working'} className="w-full">
        {state === 'working' ? '写しをつくっています' : 'カード画像をつくって共有'}
      </Button>
      {state === 'saved' && (
        <p className="mt-2 text-center font-mincho text-xs text-ink-500 dark:text-ink-400">
          画像を保存しました。投稿画面で添えてください
        </p>
      )}
      {state === 'error' && (
        <p className="mt-2 text-center font-mincho text-xs text-ink-500 dark:text-ink-400">
          写しをつくれませんでした
        </p>
      )}

      {/* 画面には出さないが、画像化のために実体は描いておく */}
      <div
        aria-hidden
        style={{
          position: 'fixed',
          left: -10000,
          top: 0,
          pointerEvents: 'none',
          opacity: 0,
        }}
      >
        <ShareCard ref={cardRef} player={player} />
      </div>
    </div>
  )
}
