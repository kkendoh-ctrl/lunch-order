import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { Session, User } from '@supabase/supabase-js'
import { supabase } from './supabase'

type AuthValue = {
  session: Session | null
  user: User | null
  loading: boolean
  /** XのユーザーID。Xログインでなければ null。 */
  xUserId: string | null
  xHandle: string | null
  signInWithX: () => Promise<void>
  signInWithEmail: (email: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

/** JWT の形は provider によって違うので、拾えるところから拾う。 */
function readXIdentity(user: User | null) {
  if (!user) return { xUserId: null, xHandle: null }
  const identity = user.identities?.find((i) => i.provider === 'twitter')
  const data = (identity?.identity_data ?? {}) as Record<string, unknown>
  const meta = (user.user_metadata ?? {}) as Record<string, unknown>

  const xUserId =
    (identity?.id as string | undefined) ??
    (data.provider_id as string | undefined) ??
    (data.sub as string | undefined) ??
    (meta.provider_id as string | undefined) ??
    null

  const xHandle =
    (data.user_name as string | undefined) ??
    (data.preferred_username as string | undefined) ??
    (meta.user_name as string | undefined) ??
    (meta.preferred_username as string | undefined) ??
    null

  return { xUserId, xHandle }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    supabase.auth.getSession().then(({ data }) => {
      if (!alive) return
      setSession(data.session)
      setLoading(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next)
      setLoading(false)
    })
    return () => {
      alive = false
      sub.subscription.unsubscribe()
    }
  }, [])

  const value = useMemo<AuthValue>(() => {
    const user = session?.user ?? null
    const { xUserId, xHandle } = readXIdentity(user)
    return {
      session,
      user,
      loading,
      xUserId,
      xHandle,
      async signInWithX() {
        const { error } = await supabase.auth.signInWithOAuth({
          provider: 'twitter',
          options: { redirectTo: `${window.location.origin}/onboarding` },
        })
        if (error) throw error
      },
      async signInWithEmail(email: string) {
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: `${window.location.origin}/onboarding` },
        })
        if (error) throw error
      },
      async signOut() {
        await supabase.auth.signOut()
      },
    }
  }, [session, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('AuthProvider の外で useAuth は使えません')
  return ctx
}
