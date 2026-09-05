import { forwardRef } from 'react'
import { avatarPublicUrl } from '../lib/supabase'
import { regionById } from '../constants/prefectures'
import { dexNo } from './DexCard'
import type { PlayerWithTeam } from '../types/database'

const GOTHIC =
  'system-ui, -apple-system, "Hiragino Kaku Gothic ProN", "Noto Sans JP", Meiryo, sans-serif'
const MINCHO =
  '"Hiragino Mincho ProN", "Yu Mincho", "Noto Serif JP", "MS PMincho", serif'

/**
 * 共有画像(PNG)専用の版。
 * 画面用の見た目とは別に、色を直接書いて明暗テーマの影響を受けないようにしている。
 */
export const ShareCard = forwardRef<HTMLDivElement, { player: PlayerWithTeam }>(
  function ShareCard({ player }, ref) {
    const region = regionById(player.region_id)
    const accent = region?.accent ?? '#83857a'
    const avatar = avatarPublicUrl(player.avatar_url)

    return (
      <div
        ref={ref}
        style={{
          width: 640,
          background: '#ffffff',
          color: '#181a17',
          fontFamily: GOTHIC,
          borderTop: `8px solid ${accent}`,
          padding: 40,
          boxSizing: 'border-box',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span
            style={{
              color: accent,
              fontSize: 22,
              letterSpacing: '0.2em',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            }}
          >
            {dexNo(player.dex_number)}
          </span>
          <span style={{ fontSize: 18, letterSpacing: '0.3em', color: '#83857a' }}>
            {region?.name ?? '—'}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 24, marginTop: 28, alignItems: 'flex-start' }}>
          <div
            style={{
              width: 176,
              height: 176,
              flexShrink: 0,
              borderRadius: 16,
              overflow: 'hidden',
              background: `${accent}22`,
              outline: `1px solid ${accent}44`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {avatar ? (
              <img
                src={avatar}
                alt=""
                crossOrigin="anonymous"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <span style={{ fontFamily: MINCHO, fontSize: 64, color: accent }}>
                {player.nickname.slice(0, 1)}
              </span>
            )}
          </div>

          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
              {player.is_legend && (
                <span
                  style={{
                    background: accent,
                    color: '#0f100e',
                    fontSize: 12,
                    fontWeight: 700,
                    letterSpacing: '0.2em',
                    padding: '3px 8px',
                    borderRadius: 4,
                  }}
                >
                  伝説
                </span>
              )}
            </div>
            <div style={{ fontSize: 40, fontWeight: 700, lineHeight: 1.2 }}>
              {player.nickname}
            </div>
            <div style={{ marginTop: 12, fontSize: 16, color: '#63655c', lineHeight: 1.8 }}>
              <div>所属　{player.teams?.name ?? '無所属'}</div>
              <div>
                拠点　{player.prefecture}
                {player.home_ground ? ` / ${player.home_ground}` : ''}
              </div>
            </div>
            {player.style_tags.length > 0 && (
              <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                {player.style_tags.map((t) => (
                  <span
                    key={t}
                    style={{
                      border: `1px solid ${accent}66`,
                      background: `${accent}14`,
                      color: '#4c4e47',
                      borderRadius: 999,
                      padding: '3px 10px',
                      fontSize: 14,
                    }}
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div
          style={{
            marginTop: 32,
            paddingTop: 24,
            borderTop: '1px dashed #d3d3ca',
            fontFamily: MINCHO,
            fontSize: 22,
            lineHeight: 1.9,
          }}
        >
          <div>
            <span style={{ fontSize: 13, letterSpacing: '0.2em', color: '#83857a', marginRight: 10 }}>
              決め台詞
            </span>
            {player.win_phrase || '—'}
          </div>
          <div>
            <span style={{ fontSize: 13, letterSpacing: '0.2em', color: '#83857a', marginRight: 10 }}>
              鳴き声
            </span>
            {player.miss_cry || '—'}
          </div>
        </div>

        <div
          style={{
            marginTop: 32,
            textAlign: 'center',
            fontSize: 13,
            letterSpacing: '0.35em',
            color: '#adaea1',
          }}
        >
          全国モルッカー図鑑
        </div>
      </div>
    )
  },
)
