import { useTranslation } from 'react-i18next'
import type { AttendeeStatus } from '@/types/status'

/**
 * Story fe-2.4 — StatusBadge: pill + ведущая точка-dot + текст. Цвет НЕ единственный
 * носитель смысла (dot+текст) — a11y/дальтонизм. Цвета из `status-*`-токенов (fe-2.1).
 */
type Tone = 'active' | 'checking' | 'sent' | 'exported' | 'neutral'

// Статичные литералы классов — Tailwind v4 JIT не видит динамические строки `bg-${x}`.
// fg/bg/dot-токены читаются контраст-тестом из этих же строк (drift-proof, см. scripts/status-badge-contrast.test.ts).
export const TONE_CLASSES: Record<Tone, { badge: string; dot: string }> = {
  active: { badge: 'bg-status-active-tint text-status-active', dot: 'bg-status-active' },
  checking: { badge: 'bg-status-checking-tint text-status-checking', dot: 'bg-status-checking' },
  sent: { badge: 'bg-status-sent-tint text-status-sent', dot: 'bg-status-sent' },
  exported: { badge: 'bg-status-exported-tint text-status-exported', dot: 'bg-status-exported' },
  neutral: { badge: 'bg-surface-muted text-text-muted', dot: 'bg-text-muted' },
}

// Маппинг статус (state-machine) → тон. [ASSUMPTION] (свериться с Erda/дизайном):
// draft→neutral (в DESIGN нет статус-цвета под черновик); токен status-rejected (красный)
// ЗАРЕЗЕРВИРОВАН под будущий return-flow «Отклонена/Возвращена» (E3a) — здесь не используется.
const STATUS_TONE: Record<AttendeeStatus, Tone> = {
  draft: 'neutral',
  submitted: 'sent',
  in_review: 'checking',
  ready: 'active',
  exported: 'exported',
}

function toneFor(status: string): Tone {
  // defensive: неизвестный код → нейтральный тон (не падаем; список отдаёт status: string).
  return (STATUS_TONE as Record<string, Tone>)[status] ?? 'neutral'
}

export function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  const cls = TONE_CLASSES[toneFor(status)]
  // Пустой/nullish статус → '—' (не оставляем pill с одной точкой без текста — AC-3 dot+текст).
  const label = status ? t(`status:${status}`, { defaultValue: status }) : '—'
  return (
    <span
      className={
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-sm font-medium ' + cls.badge
      }
    >
      <span
        data-testid="status-dot"
        aria-hidden="true"
        className={'h-1.5 w-1.5 rounded-full ' + cls.dot}
      />
      {label}
    </span>
  )
}
