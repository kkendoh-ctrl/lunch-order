export function StyleTagChip({
  tag,
  accent,
}: {
  tag: string
  accent?: string
}) {
  return (
    <span
      className="rounded-full border px-2 py-0.5 text-[11px] tracking-wide text-ink-600 dark:text-ink-200"
      style={{
        borderColor: accent ? `${accent}66` : undefined,
        backgroundColor: accent ? `${accent}14` : undefined,
      }}
    >
      {tag}
    </span>
  )
}
