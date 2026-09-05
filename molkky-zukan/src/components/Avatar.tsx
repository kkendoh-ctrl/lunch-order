import { avatarPublicUrl } from '../lib/supabase'

/** 写真が無いときは頭文字を彫った札を出す。 */
export function Avatar({
  src,
  name,
  accent,
  className = '',
}: {
  src: string | null
  name: string
  accent?: string
  className?: string
}) {
  const url = avatarPublicUrl(src)
  if (url) {
    return (
      <img
        src={url}
        alt=""
        crossOrigin="anonymous"
        loading="lazy"
        className={`h-full w-full object-cover ${className}`}
      />
    )
  }
  return (
    <div
      className={`flex h-full w-full items-center justify-center bg-ink-100 dark:bg-ink-800 ${className}`}
      style={accent ? { backgroundColor: `${accent}22` } : undefined}
    >
      <span
        className="font-mincho text-2xl text-ink-400 dark:text-ink-500"
        style={accent ? { color: accent } : undefined}
      >
        {name.slice(0, 1)}
      </span>
    </div>
  )
}
