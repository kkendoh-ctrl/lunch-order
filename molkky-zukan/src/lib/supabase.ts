import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!url || !anonKey) {
  // 起動時に気づけるようにする。.env.local を用意すれば消える。
  console.error(
    'VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY が未設定です。.env.example を参考に .env.local を作ってください。',
  )
}

// 未設定でも起動だけはできるようにしておく（通信は当然失敗する）
const PLACEHOLDER = 'https://placeholder.supabase.co'

export const supabase = createClient(url || PLACEHOLDER, anonKey || 'anon', {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    flowType: 'pkce',
  },
})

export const AVATAR_BUCKET = 'avatars'

export function avatarPublicUrl(path: string | null): string | null {
  if (!path) return null
  if (path.startsWith('http')) return path
  return supabase.storage.from(AVATAR_BUCKET).getPublicUrl(path).data.publicUrl
}
