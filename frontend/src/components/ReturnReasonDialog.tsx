import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

interface ReturnReasonDialogProps {
  open: boolean
  pending?: boolean
  onClose: () => void
  onSubmit: (reason: string) => void
}

/**
 * Story fe-3.5 — ReturnReasonDialog. Модалка возврата заявки с ОБЯЗАТЕЛЬНОЙ причиной.
 * Нативная (без UI-зависимости): `role="dialog"` + `aria-modal` + focus-trap (ручной) + Esc +
 * возврат фокуса на триггер при закрытии. Submit `disabled` пока причина пуста (UX-DR9).
 * Открывается из detail-футера (fe-3.3 stub) и из строки очереди (инлайн, как row-approve fe-3.4).
 * Все строки через `t('reviewQueue:...')`.
 */
export function ReturnReasonDialog({
  open,
  pending = false,
  onClose,
  onSubmit,
}: ReturnReasonDialogProps) {
  const { t } = useTranslation()
  const titleId = useId()
  const descId = useId()
  const [reason, setReason] = useState('')
  const dialogRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // Элемент-триггер (для возврата фокуса при закрытии — не в document.body).
  const triggerRef = useRef<HTMLElement | null>(null)

  // При открытии: запоминаем триггер, сбрасываем причину, фокус на поле.
  useEffect(() => {
    if (!open) return
    triggerRef.current = document.activeElement as HTMLElement | null
    setReason('')
    textareaRef.current?.focus()
  }, [open])

  if (!open) return null

  const trimmed = reason.trim()
  const canSubmit = trimmed.length > 0 && !pending

  function close() {
    onClose()
    // Возврат фокуса на кнопку-триггер (синхронно — до того как unmount уронит фокус в body).
    triggerRef.current?.focus()
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault()
      close()
      return
    }
    if (e.key !== 'Tab') return
    // focus-trap: Tab/Shift+Tab циклятся по фокусируемым внутри модалки (не выходят за неё).
    const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )
    if (!focusables || focusables.length === 0) return
    const first = focusables[0]
    const last = focusables[focusables.length - 1]
    const active = document.activeElement
    if (e.shiftKey && active === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && active === last) {
      e.preventDefault()
      first.focus()
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) close()
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        onKeyDown={onKeyDown}
        className="w-full max-w-md rounded-lg border border-border bg-surface p-6 shadow-lg"
      >
        <h2 id={titleId} className="text-[15px] font-[650] tracking-[-0.01em] text-text">
          {t('reviewQueue:return_dialog_title')}
        </h2>
        <p id={descId} className="mt-1 text-sm text-text-muted">
          {t('reviewQueue:return_dialog_desc')}
        </p>
        <label
          htmlFor={`${titleId}-reason`}
          className="mt-4 block text-sm font-medium text-text"
        >
          {t('reviewQueue:return_reason_label')}
        </label>
        <textarea
          id={`${titleId}-reason`}
          ref={textareaRef}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          placeholder={t('reviewQueue:return_reason_placeholder')}
          className="mt-1 w-full rounded-md border border-input-border bg-surface px-3 py-2 text-base text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        />
        <div className="mt-5 flex justify-end gap-3">
          <Button variant="outline" type="button" onClick={close} disabled={pending}>
            {t('reviewQueue:return_cancel')}
          </Button>
          <Button
            variant="default"
            type="button"
            disabled={!canSubmit}
            onClick={() => onSubmit(trimmed)}
          >
            {t('reviewQueue:return_submit')}
          </Button>
        </div>
      </div>
    </div>
  )
}
