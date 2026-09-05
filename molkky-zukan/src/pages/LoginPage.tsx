import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { AuthPanel } from '../components/AuthPanel'
import { Loading } from '../components/ui'

export function LoginPage() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next') ?? '/onboarding'

  useEffect(() => {
    if (!loading && user) navigate(next, { replace: true })
  }, [loading, user, next, navigate])

  if (loading) return <Loading />

  return (
    <div className="space-y-8 py-6">
      <div className="text-center">
        <h1 className="font-mincho text-xl">記録をはじめる</h1>
        <p className="mt-2 text-xs text-ink-400 dark:text-ink-500">
          自分のカードを作るにはログインが必要です
        </p>
      </div>
      <AuthPanel />
    </div>
  )
}
