import { useTranslation } from 'react-i18next'
import { statusKey } from '@/lib/attendeeStatus'
import { cn } from '@/lib/utils'

// Этап D: статус участника всегда текстом; цвет — дополнительный признак.
// Тона из отчёта 05: внимание — ждёт проверяющего, успех — допущен, ошибка — возвращён.
// Пары текст/фон проверяет scripts/status-badge-contrast.test.ts (≥ 4,5:1).
export const TONE_CLASSES: Record<string, string> = {
  draft: 'bg-info-bg text-info',
  returned: 'bg-danger-bg text-danger',
  submitted: 'bg-warning-bg text-warning',
  in_review: 'bg-warning-bg text-warning',
  ready: 'bg-success-bg text-success',
  exported: 'bg-success-bg text-success',
  unknown: 'bg-section text-ink',
}

export function StatusBadge({
  status,
  returned = false,
  className,
}: {
  status: string
  returned?: boolean
  className?: string
}) {
  const { t } = useTranslation()
  const tone = returned && status === 'draft' ? TONE_CLASSES.returned : (TONE_CLASSES[status] ?? TONE_CLASSES.unknown)
  // Пустой статус — прочерк; неизвестный код — сам код (не теряем значение молча).
  const label = status ? t(statusKey(status, returned), { defaultValue: status }) : '—'
  return (
    <span
      className={cn(
        'inline-block rounded-md px-2 py-0.5 text-sm font-semibold leading-5 [overflow-wrap:anywhere]',
        tone,
        className,
      )}
    >
      {label}
    </span>
  )
}
