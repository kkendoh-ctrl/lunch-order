export type ThemeMode = 'light' | 'dark' | 'system'

const KEY = 'zukan.theme'

export function readTheme(): ThemeMode {
  const stored = localStorage.getItem(KEY)
  return stored === 'light' || stored === 'dark' ? stored : 'system'
}

export function applyTheme(mode: ThemeMode) {
  const dark =
    mode === 'dark' ||
    (mode === 'system' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
  if (mode === 'system') localStorage.removeItem(KEY)
  else localStorage.setItem(KEY, mode)
}

export function initTheme() {
  applyTheme(readTheme())
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => {
      if (readTheme() === 'system') applyTheme('system')
    })
}
