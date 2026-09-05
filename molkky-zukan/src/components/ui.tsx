import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { MESSAGES } from '../constants/messages'

export function Button({
  variant = 'primary',
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'quiet'
}) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition disabled:opacity-40 disabled:pointer-events-none'
  const styles = {
    primary:
      'bg-ink-900 text-ink-50 hover:bg-ink-800 dark:bg-amber-300 dark:text-ink-950 dark:hover:bg-amber-200',
    ghost:
      'border border-ink-300 text-ink-800 hover:bg-ink-100 dark:border-ink-700 dark:text-ink-100 dark:hover:bg-ink-800',
    quiet: 'text-ink-500 hover:text-ink-800 dark:hover:text-ink-100',
  }[variant]
  return <button className={`${base} ${styles} ${className}`} {...rest} />
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="block space-y-1.5">
      <span className="flex items-baseline justify-between">
        <span className="text-xs font-medium tracking-wide text-ink-500 dark:text-ink-300">
          {label}
        </span>
        {hint && (
          <span className="text-[11px] text-ink-400 dark:text-ink-500">{hint}</span>
        )}
      </span>
      {children}
    </label>
  )
}

export const inputClass =
  'w-full rounded-lg border border-ink-200 bg-white px-3 py-2.5 text-sm text-ink-900 outline-none transition placeholder:text-ink-300 focus:border-amber-400 dark:border-ink-700 dark:bg-ink-900 dark:text-ink-50 dark:placeholder:text-ink-600'

export function Loading({ label = MESSAGES.loading }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-ink-400 dark:text-ink-500">
      <span className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
      <p className="text-xs tracking-widest">{label}</p>
    </div>
  )
}

export function ErrorState({ error }: { error: unknown }) {
  const detail = error instanceof Error ? error.message : String(error ?? '')
  return (
    <div className="mx-auto max-w-sm py-16 text-center">
      <p className="font-mincho text-lg text-ink-700 dark:text-ink-200">
        {MESSAGES.error}
      </p>
      {detail && (
        <p className="mt-2 break-all text-[11px] text-ink-400 dark:text-ink-500">
          {detail}
        </p>
      )}
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="py-16 text-center font-mincho text-sm text-ink-400 dark:text-ink-500">
      {children}
    </p>
  )
}
