import { useState } from 'react'
import { useAuth } from '../lib/auth'
import { Button, Field, inputClass } from './ui'

/** Xログインを第一に、メールログインも用意する。 */
export function AuthPanel() {
  const { signInWithX, signInWithEmail } = useAuth()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  return (
    <div className="space-y-6">
      <Button
        className="w-full py-3"
        disabled={busy}
        onClick={async () => {
          setError(null)
          setBusy(true)
          try {
            await signInWithX()
          } catch (e) {
            setError(e instanceof Error ? e.message : 'ログインできませんでした')
            setBusy(false)
          }
        }}
      >
        Xでログイン
      </Button>
      <p className="-mt-4 text-center text-[11px] text-ink-400 dark:text-ink-500">
        すでに下書きカードがある場合、Xでログインすると自動で見つかります
      </p>

      <div className="flex items-center gap-3 text-[11px] text-ink-300 dark:text-ink-600">
        <span className="h-px flex-1 bg-ink-200 dark:bg-ink-800" />
        または
        <span className="h-px flex-1 bg-ink-200 dark:bg-ink-800" />
      </div>

      {sent ? (
        <p className="text-center font-mincho text-sm text-ink-600 dark:text-ink-300">
          メールを送りました。届いたリンクから戻ってきてください。
        </p>
      ) : (
        <form
          className="space-y-3"
          onSubmit={async (e) => {
            e.preventDefault()
            setError(null)
            setBusy(true)
            try {
              await signInWithEmail(email)
              setSent(true)
            } catch (err) {
              setError(err instanceof Error ? err.message : '送れませんでした')
            } finally {
              setBusy(false)
            }
          }}
        >
          <Field label="メールでログイン">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="you@example.com"
            />
          </Field>
          <Button type="submit" variant="ghost" className="w-full" disabled={busy}>
            リンクを送る
          </Button>
        </form>
      )}

      {error && (
        <p className="text-center text-[11px] text-ink-500 dark:text-ink-400">{error}</p>
      )}
    </div>
  )
}
