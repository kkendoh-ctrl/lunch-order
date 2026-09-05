import { useState } from 'react'
import { Modal } from './Modal'
import { Button, Field, inputClass } from './ui'
import { useReport, useRequestDeletion } from '../hooks/useZukan'

/** 通報。同じカードに3件たまると自動で見えなくなる。 */
export function ReportButton({
  playerId,
  reporterId,
}: {
  playerId: string
  reporterId: string | null
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [done, setDone] = useState(false)
  const report = useReport()

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-[11px] text-ink-400 underline underline-offset-2 hover:text-ink-600 dark:text-ink-500 dark:hover:text-ink-300"
      >
        気になる点を知らせる
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title="気になる点を知らせる">
        {done ? (
          <p className="font-mincho text-sm text-ink-600 dark:text-ink-300">
            受け取りました。同じ知らせが重なると、このカードは自動で見えなくなります。
          </p>
        ) : (
          <form
            className="space-y-4"
            onSubmit={async (e) => {
              e.preventDefault()
              await report.mutateAsync({ targetId: playerId, reason, reporterId })
              setDone(true)
            }}
          >
            <Field label="どこが気になりますか" hint="400字まで">
              <textarea
                required
                maxLength={400}
                rows={4}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className={inputClass}
                placeholder="本人ではない、内容が不適切、など"
              />
            </Field>
            {report.isError && (
              <p className="text-xs text-ink-500">送れませんでした。時間をおいて試してください。</p>
            )}
            <div className="flex gap-2">
              <Button type="submit" disabled={report.isPending} className="flex-1">
                送る
              </Button>
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                やめる
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </>
  )
}

/** 削除依頼。未確認カードは受け付けた時点で非公開になる。 */
export function DeletionRequestButton({
  playerId,
  isUnclaimed,
}: {
  playerId: string
  isUnclaimed: boolean
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [contact, setContact] = useState('')
  const [done, setDone] = useState(false)
  const request = useRequestDeletion()

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-[11px] text-ink-400 underline underline-offset-2 hover:text-ink-600 dark:text-ink-500 dark:hover:text-ink-300"
      >
        削除を依頼する
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title="削除を依頼する">
        {done ? (
          <p className="font-mincho text-sm text-ink-600 dark:text-ink-300">
            受け付けました。このカードは図鑑から見えなくなりました。
          </p>
        ) : (
          <form
            className="space-y-4"
            onSubmit={async (e) => {
              e.preventDefault()
              await request.mutateAsync({ playerId, reason, contact })
              setDone(true)
            }}
          >
            <p className="font-mincho text-xs leading-relaxed text-ink-500 dark:text-ink-400">
              {isUnclaimed
                ? '未確認カードは、依頼を受け取った時点ですぐ非公開にします。運営の確認は挟みません。'
                : '本人確認済みのカードは、持ち主本人からの依頼のときにすぐ非公開にします。'}
            </p>
            <Field label="理由" hint="任意">
              <textarea
                rows={3}
                maxLength={400}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="連絡先" hint="任意">
              <input
                type="text"
                maxLength={120}
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                className={inputClass}
                placeholder="Xのアカウント / メールなど"
              />
            </Field>
            {request.isError && (
              <p className="text-xs text-ink-500">送れませんでした。時間をおいて試してください。</p>
            )}
            <div className="flex gap-2">
              <Button type="submit" disabled={request.isPending} className="flex-1">
                依頼する
              </Button>
              <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
                やめる
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </>
  )
}
