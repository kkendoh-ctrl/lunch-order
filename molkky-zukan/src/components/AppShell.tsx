import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { applyTheme, readTheme, type ThemeMode } from '../lib/theme'

function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() => readTheme())
  useEffect(() => applyTheme(mode), [mode])

  const next: Record<ThemeMode, ThemeMode> = {
    system: 'light',
    light: 'dark',
    dark: 'system',
  }
  const label: Record<ThemeMode, string> = {
    system: '自動',
    light: '昼',
    dark: '夜',
  }
  return (
    <button
      onClick={() => setMode(next[mode])}
      className="rounded-full border border-ink-200 px-3 py-1 text-[11px] tracking-widest text-ink-500 transition hover:border-ink-300 dark:border-ink-700 dark:text-ink-400"
      aria-label="表示テーマを切り替える"
    >
      {label[mode]}
    </button>
  )
}

const tabClass = ({ isActive }: { isActive: boolean }) =>
  [
    'flex-1 py-3 text-center text-xs tracking-widest transition',
    isActive
      ? 'font-bold text-ink-900 dark:text-amber-300'
      : 'text-ink-400 dark:text-ink-500',
  ].join(' ')

export function AppShell() {
  const { pathname } = useLocation()
  const bare = pathname === '/login' || pathname === '/onboarding'

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-100 bg-ink-50/90 px-4 py-3 backdrop-blur dark:border-ink-800 dark:bg-ink-950/90">
        <NavLink to="/" className="text-sm font-bold tracking-[0.2em]">
          全国モルッカー図鑑
        </NavLink>
        <ThemeToggle />
      </header>

      <main className="flex-1 px-4 py-5">
        <Outlet />
      </main>

      {!bare && (
        <nav className="sticky bottom-0 z-30 flex border-t border-ink-100 bg-ink-50/95 backdrop-blur dark:border-ink-800 dark:bg-ink-950/95">
          <NavLink to="/" end className={tabClass}>
            図鑑
          </NavLink>
          <NavLink to="/me" className={tabClass}>
            マイカード
          </NavLink>
        </nav>
      )}
    </div>
  )
}
