import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBadge } from './StatusBadge'
import { ATTENDEE_STATUSES } from '@/types/status'

// ru-лейблы из locales/ru/status.json (vitest.setup форсит ru → t() без провайдера).
const LABELS: Record<string, string> = {
  draft: 'Черновик',
  submitted: 'Отправлен',
  in_review: 'На проверке',
  ready: 'Готов',
  exported: 'Выгружен',
}

describe('StatusBadge (fe-2.4)', () => {
  it('AC-1/AC-3: для каждого статуса присутствуют И dot (форма), И текст (не только цвет)', () => {
    for (const status of ATTENDEE_STATUSES) {
      const { unmount } = render(<StatusBadge status={status} />)
      expect(screen.getByText(LABELS[status])).toBeInTheDocument()
      const dot = screen.getByTestId('status-dot')
      expect(dot).toBeInTheDocument()
      expect(dot).toHaveAttribute('aria-hidden', 'true') // декоративна — смысл в тексте
      unmount()
    }
  })

  it('AC-1: корректные тон-токены по статусу (fill=tint, текст=основной, dot=основной)', () => {
    // [status, badge-bg(tint), badge-text, dot-bg(основной цвет)]
    const cases: Array<[string, string, string, string]> = [
      ['ready', 'bg-status-active-tint', 'text-status-active', 'bg-status-active'],
      ['in_review', 'bg-status-checking-tint', 'text-status-checking', 'bg-status-checking'],
      ['submitted', 'bg-status-sent-tint', 'text-status-sent', 'bg-status-sent'],
      ['exported', 'bg-status-exported-tint', 'text-status-exported', 'bg-status-exported'],
      ['draft', 'bg-surface-muted', 'text-text-muted', 'bg-text-muted'],
    ]
    for (const [status, bg, fg, dotBg] of cases) {
      const { container, unmount } = render(<StatusBadge status={status} />)
      const badge = container.firstElementChild as HTMLElement
      expect(badge).toHaveClass(bg)
      expect(badge).toHaveClass(fg)
      expect(badge).toHaveClass('rounded-full') // pill
      // точка-dot несёт основной статус-цвет (colorblind-избыточность)
      expect(screen.getByTestId('status-dot')).toHaveClass(dotBg)
      unmount()
    }
  })

  it('AC-1: неизвестный статус → нейтральный тон + сырой код как текст (не падает)', () => {
    const { container } = render(<StatusBadge status="bogus" />)
    expect(screen.getByText('bogus')).toBeInTheDocument()
    expect(container.firstElementChild).toHaveClass('bg-surface-muted')
    expect(screen.getByTestId('status-dot')).toBeInTheDocument()
  })
})
