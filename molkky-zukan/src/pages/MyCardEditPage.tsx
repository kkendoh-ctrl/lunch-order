import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { useMyPlayer, useUpdateMyPlayer, useUploadAvatar } from '../hooks/useZukan'
import {
  AvatarPicker,
  PrefectureSelect,
  StyleTagPicker,
  TeamSelect,
} from '../components/formFields'
import { Button, Field, Loading, inputClass } from '../components/ui'
import { DexCard } from '../components/DexCard'
import { MESSAGES } from '../constants/messages'
import type { StyleTag } from '../constants/styleTags'
import type { Visibility } from '../types/database'

const VISIBILITY_LABEL: Record<Visibility, string> = {
  public: '全員に見せる',
  members: 'ログインした人だけに見せる',
  hidden: '誰にも見せない',
}

export function MyCardEditPage() {
  const navigate = useNavigate()
  const { user, loading, signOut } = useAuth()
  const { data: player, isLoading } = useMyPlayer(user?.id ?? null)
  const update = useUpdateMyPlayer()
  const uploadAvatar = useUploadAvatar()

  const [nickname, setNickname] = useState('')
  const [realName, setRealName] = useState('')
  const [prefecture, setPrefecture] = useState('')
  const [teamId, setTeamId] = useState<string | null>(null)
  const [homeGround, setHomeGround] = useState('')
  const [winPhrase, setWinPhrase] = useState('')
  const [missCry, setMissCry] = useState('')
  const [styleTags, setStyleTags] = useState<StyleTag[]>([])
  const [visibility, setVisibility] = useState<Visibility>('public')
  const [file, setFile] = useState<File | null>(null)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!player) return
    setNickname(player.nickname)
    setRealName(player.real_name ?? '')
    setPrefecture(player.prefecture)
    setTeamId(player.team_id)
    setHomeGround(player.home_ground ?? '')
    setWinPhrase(player.win_phrase ?? '')
    setMissCry(player.miss_cry ?? '')
    setStyleTags(player.style_tags ?? [])
    setVisibility(player.visibility)
  }, [player])

  useEffect(() => {
    if (!loading && !user) navigate('/login?next=/me', { replace: true })
    if (!loading && user && !isLoading && !player) {
      navigate('/onboarding', { replace: true })
    }
  }, [loading, user, isLoading, player, navigate])

  if (loading || isLoading || !player || !user) return <Loading />

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (!player || !user) return
    setError(null)
    setSaved(false)
    try {
      let avatarPath = player.avatar_url
      if (file) {
        avatarPath = await uploadAvatar.mutateAsync({ userId: user.id, file })
      }
      await update.mutateAsync({
        id: player.id,
        draft: {
          nickname: nickname.trim(),
          real_name: realName.trim() || null,
          team_id: teamId,
          prefecture,
          home_ground: homeGround.trim() || null,
          avatar_url: avatarPath,
          win_phrase: winPhrase.trim() || null,
          miss_cry: missCry.trim() || null,
          style_tags: styleTags,
          visibility,
        },
      })
      setFile(null)
      setSaved(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : '記録できませんでした')
    }
  }

  const busy = update.isPending || uploadAvatar.isPending

  return (
    <div className="space-y-6">
      <DexCard player={player} showBadges={false} />

      <div className="flex items-center justify-between">
        <Link
          to={`/card/${player.id}`}
          className="text-[11px] text-ink-400 underline underline-offset-2 dark:text-ink-500"
        >
          図鑑での見え方をみる
        </Link>
        <button
          onClick={() => signOut()}
          className="text-[11px] text-ink-400 underline underline-offset-2 dark:text-ink-500"
        >
          ログアウト
        </button>
      </div>

      <form onSubmit={save} className="space-y-5">
        <AvatarPicker
          currentUrl={player.avatar_url}
          nickname={nickname}
          file={file}
          onPick={setFile}
        />

        <Field label="ニックネーム" hint="20字まで">
          <input
            required
            maxLength={20}
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="本名" hint="任意・図鑑には出しません">
          <input
            maxLength={40}
            value={realName}
            onChange={(e) => setRealName(e.target.value)}
            className={inputClass}
          />
        </Field>

        <PrefectureSelect value={prefecture} onChange={setPrefecture} />

        <TeamSelect
          value={teamId}
          onChange={setTeamId}
          prefecture={prefecture}
          userId={user.id}
        />

        <Field label="主な活動場所" hint="任意">
          <input
            maxLength={60}
            value={homeGround}
            onChange={(e) => setHomeGround(e.target.value)}
            className={inputClass}
            placeholder="◯◯河川敷、△△体育館 など"
          />
        </Field>

        <StyleTagPicker value={styleTags} onChange={setStyleTags} />

        <Field label="決め台詞" hint={`${winPhrase.length}/40`}>
          <input
            maxLength={40}
            value={winPhrase}
            onChange={(e) => setWinPhrase(e.target.value)}
            className={`${inputClass} font-mincho`}
          />
        </Field>

        <Field label="鳴き声" hint={`${missCry.length}/20`}>
          <input
            maxLength={20}
            value={missCry}
            onChange={(e) => setMissCry(e.target.value)}
            className={`${inputClass} font-mincho`}
          />
        </Field>

        <Field label="公開範囲">
          <select
            value={visibility}
            onChange={(e) => setVisibility(e.target.value as Visibility)}
            className={inputClass}
          >
            {(Object.keys(VISIBILITY_LABEL) as Visibility[]).map((v) => (
              <option key={v} value={v}>
                {VISIBILITY_LABEL[v]}
              </option>
            ))}
          </select>
        </Field>

        {error && <p className="text-xs text-ink-500 dark:text-ink-400">{error}</p>}
        {saved && (
          <p className="font-mincho text-xs text-ink-500 dark:text-ink-400">
            {MESSAGES.saved}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? MESSAGES.saving : '記録する'}
        </Button>
      </form>
    </div>
  )
}
