import { statusLabel } from '@/lib/attendeeStatus'
import { cn } from '@/lib/utils'

// Этап D: статус участника всегда текстом; цвет — дополнительный признак.
// Тона из отчёта 05: внимание — ждёт проверяющего, успех — допущен, ошибка — возвращён.
const TONE: Record<string, string> = {
  draft: 'bg-info-bg text-info',
  submitted: 'bg-warning-bg text-warning',
  in_review: 'bg-warning-bg text-warning',
  ready: 'bg-success-bg text-success',
  exported: 'bg-success-bg text-success',
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
  const tone = returned && status === 'draft' ? 'bg-danger-bg text-danger' : (TONE[status] ?? 'bg-section text-ink')
  return (
    <span
      className={cn(
        'inline-block rounded-md px-2 py-0.5 text-sm font-semibold leading-5 [overflow-wrap:anywhere]',
        tone,
        className,
      )}
    >
      {statusLabel(status, returned)}
    </span>
  )
}
