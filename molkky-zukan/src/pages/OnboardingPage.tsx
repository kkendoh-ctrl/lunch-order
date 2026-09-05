import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import {
  useClaimCard,
  useCreateMyPlayer,
  useMyPlayer,
  useUnclaimedCard,
  useUploadAvatar,
} from '../hooks/useZukan'
import { AuthPanel } from '../components/AuthPanel'
import {
  AvatarPicker,
  PrefectureSelect,
  TeamSelect,
} from '../components/formFields'
import { Button, Field, Loading, inputClass } from '../components/ui'
import { isIos, isStandalone } from '../lib/install'
import { regionOf } from '../constants/prefectures'

const STEPS = ['なまえ', 'ばしょ', 'なかま', 'すがた', 'ことば'] as const

export function OnboardingPage() {
  const navigate = useNavigate()
  const { user, loading, xUserId, xHandle } = useAuth()
  const { data: myPlayer, isLoading: loadingMine } = useMyPlayer(user?.id ?? null)
  const { data: unclaimed, isLoading: loadingUnclaimed } = useUnclaimedCard(
    !!user && !!xUserId,
  )
  const claim = useClaimCard()
  const createPlayer = useCreateMyPlayer()
  const uploadAvatar = useUploadAvatar()

  const [step, setStep] = useState(0)
  const [nickname, setNickname] = useState('')
  const [prefecture, setPrefecture] = useState('')
  const [teamId, setTeamId] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [winPhrase, setWinPhrase] = useState('')
  const [missCry, setMissCry] = useState('')
  const [created, setCreated] = useState(false)
  const [dismissedUnclaimed, setDismissedUnclaimed] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!loading && !loadingMine && myPlayer && !created) {
      navigate('/me', { replace: true })
    }
  }, [loading, loadingMine, myPlayer, created, navigate])

  if (loading || (user && (loadingMine || loadingUnclaimed))) return <Loading />

  // --- 未ログイン ---------------------------------------------------------
  if (!user) {
    return (
      <div className="space-y-8 py-6">
        <div className="text-center">
          <h1 className="font-mincho text-xl">全国モルッカー図鑑</h1>
          <p className="mt-2 font-mincho text-sm leading-relaxed text-ink-500 dark:text-ink-400">
            投げる人を、地方ごとに記録していく。
            <br />
            まずは自分の1枚から。
          </p>
        </div>
        <AuthPanel />
      </div>
    )
  }

  // --- 下書きカードが見つかった ------------------------------------------
  if (unclaimed && !created && !dismissedUnclaimed) {
    return (
      <div className="space-y-6 py-6">
        <div className="text-center">
          <h1 className="font-mincho text-xl">あなたのカードが見つかりました</h1>
          <p className="mt-2 text-xs leading-relaxed text-ink-400 dark:text-ink-500">
            Xで公開されているプロフィールから作られた下書きです。
            <br />
            本人確認すると、内容を自分で書き換えられます。
          </p>
        </div>

        <div className="rounded-xl bg-white p-4 text-center shadow-card dark:bg-ink-900">
          <p className="font-mono text-[11px] tracking-widest text-ink-400">
            No.{String(unclaimed.dex_number).padStart(4, '0')}
          </p>
          <p className="mt-1 text-lg font-bold">{unclaimed.nickname}</p>
          <p className="text-[11px] text-ink-400 dark:text-ink-500">
            {unclaimed.prefecture} / {regionOf(unclaimed.prefecture)?.name}
          </p>
        </div>

        {error && (
          <p className="text-center text-[11px] text-ink-500 dark:text-ink-400">{error}</p>
        )}

        <div className="space-y-2">
          <Button
            className="w-full"
            disabled={claim.isPending}
            onClick={async () => {
              setError(null)
              try {
                await claim.mutateAsync(unclaimed.id)
                navigate('/me', { replace: true })
              } catch (e) {
                setError(e instanceof Error ? e.message : '本人確認できませんでした')
              }
            }}
          >
            これは自分のカードです
          </Button>
          <Button
            variant="ghost"
            className="w-full"
            onClick={() => setDismissedUnclaimed(true)}
          >
            自分ではないので、新しく作る
          </Button>
        </div>
      </div>
    )
  }

  // --- 作成できた: ホーム画面への追加を案内 --------------------------------
  if (created && myPlayer) {
    return (
      <div className="space-y-6 py-6 text-center">
        <h1 className="font-mincho text-xl">カードができました</h1>
        <p className="font-mincho text-sm text-ink-500 dark:text-ink-400">
          No.{String(myPlayer.dex_number).padStart(4, '0')} として記録しました。
        </p>

        {!isStandalone() && (
          <div className="rounded-xl border border-dashed border-ink-300 p-4 text-left dark:border-ink-700">
            <p className="text-sm font-bold">ホーム画面に追加してください</p>
            <p className="mt-2 text-[11px] leading-relaxed text-ink-500 dark:text-ink-400">
              {isIos()
                ? 'Safariの共有ボタン（□に↑）→「ホーム画面に追加」。iPhoneでは、ホーム画面に追加しないと通知を受け取れません。'
                : 'ブラウザのメニュー →「アプリをインストール」または「ホーム画面に追加」。'}
            </p>
          </div>
        )}

        <div className="space-y-2">
          <Button className="w-full" onClick={() => navigate('/me')}>
            カードを仕上げる
          </Button>
          <Button variant="ghost" className="w-full" onClick={() => navigate('/')}>
            図鑑を見る
          </Button>
        </div>
      </div>
    )
  }

  // --- 新規作成ウィザード -------------------------------------------------
  const canNext = [
    nickname.trim().length > 0,
    prefecture.length > 0,
    true,
    true,
    true,
  ][step]

  async function finish() {
    if (!user) return
    setError(null)
    try {
      let avatarPath: string | null = null
      if (file) {
        avatarPath = await uploadAvatar.mutateAsync({ userId: user.id, file })
      }
      await createPlayer.mutateAsync({
        userId: user.id,
        xUserId,
        xHandle,
        draft: {
          nickname: nickname.trim(),
          real_name: null,
          team_id: teamId,
          prefecture,
          home_ground: null,
          avatar_url: avatarPath,
          win_phrase: winPhrase.trim() || null,
          miss_cry: missCry.trim() || null,
          style_tags: [],
          visibility: 'public',
        },
      })
      setCreated(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : '記録できませんでした')
    }
  }

  return (
    <div className="space-y-6 py-4">
      <div className="flex gap-1.5">
        {STEPS.map((label, i) => (
          <div key={label} className="flex-1 space-y-1">
            <div
              className={[
                'h-1 rounded-full',
                i <= step ? 'bg-ink-900 dark:bg-amber-300' : 'bg-ink-200 dark:bg-ink-800',
              ].join(' ')}
            />
            <p
              className={[
                'text-center text-[10px] tracking-widest',
                i === step ? 'text-ink-700 dark:text-ink-200' : 'text-ink-300 dark:text-ink-600',
              ].join(' ')}
            >
              {label}
            </p>
          </div>
        ))}
      </div>

      <div className="min-h-[220px] space-y-4">
        {step === 0 && (
          <Field label="ニックネーム" hint="20字まで">
            <input
              autoFocus
              maxLength={20}
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              className={inputClass}
              placeholder="図鑑に載る名前"
            />
          </Field>
        )}

        {step === 1 && (
          <PrefectureSelect value={prefecture} onChange={setPrefecture} />
        )}

        {step === 2 && (
          <TeamSelect
            value={teamId}
            onChange={setTeamId}
            prefecture={prefecture}
            userId={user.id}
          />
        )}

        {step === 3 && (
          <div className="space-y-3">
            <p className="text-xs text-ink-400 dark:text-ink-500">
              写真はあとからでも差し替えられます。
            </p>
            <AvatarPicker
              currentUrl={null}
              nickname={nickname}
              file={file}
              onPick={setFile}
            />
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <Field label="決め台詞" hint="40字まで・あとでも可">
              <input
                maxLength={40}
                value={winPhrase}
                onChange={(e) => setWinPhrase(e.target.value)}
                className={`${inputClass} font-mincho`}
                placeholder="勝ったときに言いたいこと"
              />
            </Field>
            <Field label="鳴き声" hint="20字まで・あとでも可">
              <input
                maxLength={20}
                value={missCry}
                onChange={(e) => setMissCry(e.target.value)}
                className={`${inputClass} font-mincho`}
                placeholder="外したときに出る声"
              />
            </Field>
          </div>
        )}
      </div>

      {error && (
        <p className="text-center text-[11px] text-ink-500 dark:text-ink-400">{error}</p>
      )}

      <div className="flex gap-2">
        {step > 0 && (
          <Button variant="ghost" onClick={() => setStep(step - 1)}>
            もどる
          </Button>
        )}
        {step < STEPS.length - 1 ? (
          <Button
            className="flex-1"
            disabled={!canNext}
            onClick={() => setStep(step + 1)}
          >
            つぎへ
          </Button>
        ) : (
          <Button
            className="flex-1"
            disabled={createPlayer.isPending || uploadAvatar.isPending}
            onClick={finish}
          >
            {createPlayer.isPending || uploadAvatar.isPending
              ? '記録しています'
              : 'カードを作る'}
          </Button>
        )}
      </div>

      {step === 4 && (
        <button
          onClick={finish}
          className="mx-auto block text-[11px] text-ink-400 underline underline-offset-2 dark:text-ink-500"
        >
          あとで書く
        </button>
      )}
    </div>
  )
}
