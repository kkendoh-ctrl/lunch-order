import { FEATURES } from '../lib/features'

/**
 * バッジ枠。フェーズ1は枠だけ。
 * フェーズ2で VITE_FEATURE_BADGES を立てると中身が入る。
 */
export function BadgeSlots({ count = 8 }: { count?: number }) {
  return (
    <div>
      <p className="mb-2 text-[11px] tracking-widest text-ink-400 dark:text-ink-500">
        バッジ
      </p>
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: count }).map((_, i) => (
          <span
            key={i}
            className="h-7 w-7 rounded-full border border-dashed border-ink-200 dark:border-ink-700"
            aria-hidden
          />
        ))}
      </div>
      {!FEATURES.badges && (
        <p className="mt-2 font-mincho text-[11px] text-ink-400 dark:text-ink-500">
          門番はまだ現れていない
        </p>
      )}
    </div>
  )
}
