import { useRef, useState } from 'react'
import { Field, inputClass } from './ui'
import { Avatar } from './Avatar'
import { PREFECTURES, regionOf } from '../constants/prefectures'
import { MAX_STYLE_TAGS, STYLE_TAGS, type StyleTag } from '../constants/styleTags'
import { useCreateTeam, useTeams } from '../hooks/useZukan'

export function PrefectureSelect({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const region = value ? regionOf(value) : undefined
  return (
    <Field label="都道府県" hint={region ? `${region.name}の図鑑に載ります` : '必須'}>
      <select
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      >
        <option value="">選んでください</option>
        {PREFECTURES.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
    </Field>
  )
}

export function TeamSelect({
  value,
  onChange,
  prefecture,
  userId,
}: {
  value: string | null
  onChange: (v: string | null) => void
  prefecture: string
  userId: string | null
}) {
  const { data: teams } = useTeams()
  const createTeam = useCreateTeam()
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  return (
    <div className="space-y-2">
      <Field label="チーム" hint="任意">
        <select
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value || null)}
          className={inputClass}
        >
          <option value="">無所属</option>
          {(teams ?? []).map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </Field>

      {creating ? (
        <div className="flex gap-2">
          <input
            className={inputClass}
            maxLength={40}
            value={newName}
            placeholder="チーム名"
            onChange={(e) => setNewName(e.target.value)}
          />
          <button
            type="button"
            disabled={!newName || !prefecture || !userId || createTeam.isPending}
            onClick={async () => {
              if (!userId) return
              const team = await createTeam.mutateAsync({
                name: newName,
                prefecture,
                userId,
              })
              onChange(team.id)
              setCreating(false)
              setNewName('')
            }}
            className="shrink-0 rounded-lg border border-ink-300 px-3 text-xs dark:border-ink-700"
          >
            作る
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="text-[11px] text-ink-400 underline underline-offset-2 dark:text-ink-500"
        >
          一覧に無いので新しく作る
        </button>
      )}
      {!prefecture && creating && (
        <p className="text-[11px] text-ink-400">先に都道府県を選んでください</p>
      )}
    </div>
  )
}

export function AvatarPicker({
  currentUrl,
  nickname,
  onPick,
  file,
}: {
  currentUrl: string | null
  nickname: string
  onPick: (file: File | null) => void
  file: File | null
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const preview = file ? URL.createObjectURL(file) : null

  return (
    <div className="flex items-center gap-4">
      <div className="h-20 w-20 shrink-0 overflow-hidden rounded-xl border border-ink-200 dark:border-ink-700">
        {preview ? (
          <img src={preview} alt="" className="h-full w-full object-cover" />
        ) : (
          <Avatar src={currentUrl} name={nickname || '？'} />
        )}
      </div>
      <div className="space-y-1">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="rounded-lg border border-ink-300 px-3 py-2 text-xs dark:border-ink-700"
        >
          写真を選ぶ
        </button>
        {file && (
          <button
            type="button"
            onClick={() => onPick(null)}
            className="block text-[11px] text-ink-400 underline underline-offset-2"
          >
            取り消す
          </button>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        />
      </div>
    </div>
  )
}

export function StyleTagPicker({
  value,
  onChange,
}: {
  value: StyleTag[]
  onChange: (v: StyleTag[]) => void
}) {
  const toggle = (tag: StyleTag) => {
    if (value.includes(tag)) onChange(value.filter((t) => t !== tag))
    else if (value.length < MAX_STYLE_TAGS) onChange([...value, tag])
  }
  return (
    <Field label="プレースタイル" hint={`${MAX_STYLE_TAGS}つまで`}>
      <div className="flex flex-wrap gap-2 pt-1">
        {STYLE_TAGS.map((tag) => {
          const on = value.includes(tag)
          return (
            <button
              key={tag}
              type="button"
              onClick={() => toggle(tag)}
              className={[
                'rounded-full border px-3 py-1.5 text-xs transition',
                on
                  ? 'border-transparent bg-ink-900 text-ink-50 dark:bg-amber-300 dark:text-ink-950'
                  : 'border-ink-200 text-ink-500 dark:border-ink-700 dark:text-ink-400',
              ].join(' ')}
            >
              {tag}
            </button>
          )
        })}
      </div>
    </Field>
  )
}
