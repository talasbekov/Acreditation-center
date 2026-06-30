import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReviewQueueItem, PaginatedReviewQueue } from '@/api/reviewQueue.schema'

const getReviewQueueMock = vi.fn()
vi.mock('@/api/reviewQueue', () => ({
  getReviewQueue: (...a: unknown[]) => getReviewQueueMock(...a),
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateMock }
})

import { ReviewQueuePage } from './ReviewQueuePage'

function item(id: number, full_name: string): ReviewQueueItem {
  return {
    id,
    full_name,
    iin_masked: '********1234',
    status: 'submitted',
    sub_event_id: 5,
    sub_event_name: 'Пресс-центр',
    problem_flags: [],
    last_return_reason: null,
    return_count: 0,
  }
}

function envelope(results: ReviewQueueItem[]): PaginatedReviewQueue {
  return { count: results.length, next: null, previous: null, results }
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/queue']}>
        <ReviewQueuePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getReviewQueueMock.mockReset()
  navigateMock.mockReset()
})

// AC-4 / UX-DR18: roving-tabindex — одна точка входа по Tab, стрелки двигают фокус по
// строкам, Enter открывает detail. Действия в строке tabIndex=-1 (Tab НЕ сквозь все строки).
describe('ReviewQueuePage roving-tabindex (fe-3.2 AC-4)', () => {
  async function setup() {
    getReviewQueueMock.mockResolvedValue(envelope([item(101, 'Алиев Бахыт'), item(102, 'Иванова Мария')]))
    renderPage()
    const r1 = (await screen.findByText('Алиев Бахыт')).closest('tr') as HTMLTableRowElement
    const r2 = (await screen.findByText('Иванова Мария')).closest('tr') as HTMLTableRowElement
    return { r1, r2 }
  }

  it('одна точка входа: первая строка tabIndex=0, остальные -1', async () => {
    const { r1, r2 } = await setup()
    expect(r1.tabIndex).toBe(0)
    expect(r2.tabIndex).toBe(-1)
  })

  it('ArrowDown перемещает фокус на следующую строку (roving)', async () => {
    const { r1, r2 } = await setup()
    r1.focus()
    expect(document.activeElement).toBe(r1)
    fireEvent.keyDown(r1, { key: 'ArrowDown' })
    expect(document.activeElement).toBe(r2)
    expect(r2.tabIndex).toBe(0)
    expect(r1.tabIndex).toBe(-1)
  })

  it('ArrowUp на первой строке не уходит за край', async () => {
    const { r1 } = await setup()
    r1.focus()
    fireEvent.keyDown(r1, { key: 'ArrowUp' })
    expect(document.activeElement).toBe(r1)
  })

  it('Enter на строке открывает detail /queue/:id', async () => {
    const { r2 } = await setup()
    r2.focus()
    fireEvent.keyDown(r2, { key: 'Enter' })
    expect(navigateMock).toHaveBeenCalledWith('/queue/102')
  })

  it('действия строки — tabIndex=-1 (Tab не проходит через 50 строк)', async () => {
    await setup()
    const reviewLinks = screen.getAllByRole('link', { name: 'Проверить' })
    for (const a of reviewLinks) expect(a.tabIndex).toBe(-1)
  })
})
