import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { runAxe, criticalOrSerious } from '@/test/axe'
import type { ReviewQueueItem, PaginatedReviewQueue } from '@/api/reviewQueue.schema'

const getReviewQueueMock = vi.fn()
const approveReviewQueueItemMock = vi.fn()
vi.mock('@/api/reviewQueue', () => ({
  getReviewQueue: (...a: unknown[]) => getReviewQueueMock(...a),
  approveReviewQueueItem: (...a: unknown[]) => approveReviewQueueItemMock(...a),
}))

const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('sonner', () => ({
  toast: {
    success: (...a: unknown[]) => toastSuccess(...a),
    error: (...a: unknown[]) => toastError(...a),
  },
}))

import { ReviewQueuePage } from './ReviewQueuePage'

function item(over: Partial<ReviewQueueItem> = {}): ReviewQueueItem {
  return {
    id: 101,
    full_name: 'Алиев Бахыт Серикулы',
    iin_masked: '********1234',
    status: 'submitted',
    sub_event_id: 5,
    sub_event_name: 'Пресс-центр',
    problem_flags: ['no_photo'],
    last_return_reason: null,
    return_count: 0,
    ...over,
  }
}

function envelope(results: ReviewQueueItem[], count: number): PaginatedReviewQueue {
  return { count, next: null, previous: null, results }
}

function renderPage(initial: string[] = ['/queue']) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initial}>
        <ReviewQueuePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getReviewQueueMock.mockReset()
  approveReviewQueueItemMock.mockReset()
  toastSuccess.mockReset()
  toastError.mockReset()
})

// fe-2.5 axe-гейт (структурный floor; контраст/target-size — Playwright/manual QA).
describe('ReviewQueuePage a11y (fe-3.2 AC-4)', () => {
  it('0 critical/serious на состоянии со строками (вкл. флаг-строку)', async () => {
    getReviewQueueMock.mockResolvedValue(
      envelope([item(), item({ id: 102, full_name: 'Иванова Мария', problem_flags: [] })], 2),
    )
    const { container } = renderPage()
    await screen.findByText('Алиев Бахыт Серикулы')
    expect(criticalOrSerious(await runAxe(container))).toEqual([])
  })

  it('0 critical/serious на пустом состоянии «всё проверено»', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([], 0))
    const { container } = renderPage()
    await waitFor(() => expect(screen.getByText('Всё проверено')).toBeInTheDocument())
    expect(criticalOrSerious(await runAxe(container))).toEqual([])
  })

  it('review P7: 0 critical/serious после approve (тающая строка + перемещённый фокус)', async () => {
    // AC-6 «после-approve» axe-floor: одобряем строку, ждём тающее состояние (pointer-events-none/
    // opacity, фокус ушёл на соседа) и гоняем axe по нему. jsdom без matchMedia → motion-safe.
    getReviewQueueMock.mockResolvedValue(
      envelope(
        [
          item({ id: 101, status: 'in_review' }),
          item({ id: 102, full_name: 'Иванова Мария', status: 'in_review', problem_flags: [] }),
        ],
        2,
      ),
    )
    approveReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'ready' })
    const { container } = renderPage()
    const tr = (await screen.findByText('Алиев Бахыт Серикулы')).closest('tr')!
    fireEvent.click(within(tr).getByRole('button', { name: 'Одобрить' }))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled())
    expect(criticalOrSerious(await runAxe(container))).toEqual([])
  })
})
