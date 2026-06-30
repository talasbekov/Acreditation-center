import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { runAxe, criticalOrSerious } from '@/test/axe'
import { ApiError } from '@/api/client'
import type { ReviewQueueDetail } from '@/api/reviewQueue.schema'

const getReviewQueueItemMock = vi.fn()
vi.mock('@/api/reviewQueue', () => ({
  getReviewQueueItem: (...a: unknown[]) => getReviewQueueItemMock(...a),
  approveReviewQueueItem: vi.fn(),
  returnReviewQueueItem: vi.fn(),
}))

const useRoleMock = vi.fn()
vi.mock('@/hooks/useRole', () => ({ useRole: () => useRoleMock() }))
vi.mock('@/lib/auth', () => ({ redirectToLogin: () => {} }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import { ApplicationDetailPage } from './ApplicationDetailPage'

function detail(over: Partial<ReviewQueueDetail> = {}): ReviewQueueDetail {
  return {
    id: 101,
    full_name: 'Алиев Бахыт Серикулы',
    iin_masked: '********1234',
    status: 'in_review',
    sub_event_id: 5,
    sub_event_name: 'Пресс-центр',
    problem_flags: ['no_photo', 'doc_unreadable'],
    last_return_reason: 'Нет фото',
    return_count: 2,
    photo: null,
    doc_scan: '/media/event_5/attendee_documents/sample.jpg',
    birth_date: '1985-12-05',
    is_resident: true,
    country: 'Казахстан',
    post: 'Корреспондент',
    transcription: 'Aliyev Bakhyt Serikuly',
    doc_type: 'passport',
    created_at: '2026-06-20T14:30:00+05:00',
    ...over,
  }
}

function renderPage(role: string | undefined = 'superuser') {
  useRoleMock.mockReturnValue(role)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/queue/101']}>
        <Routes>
          <Route path="/queue/:id" element={<ApplicationDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getReviewQueueItemMock.mockReset()
  useRoleMock.mockReset()
})

// fe-2.5 axe-гейт (структурный floor; контраст/target-size — Playwright/manual QA).
describe('ApplicationDetailPage a11y (fe-3.3 AC-11)', () => {
  it('0 critical/serious на загруженном detail (флаги + placeholder + breadcrumb)', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    const { container } = renderPage('superuser')
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    expect(criticalOrSerious(await runAxe(container))).toEqual([])
  })

  it('0 critical/serious в ветке оператора (статичный контекст)', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    const { container } = renderPage('operator')
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    expect(criticalOrSerious(await runAxe(container))).toEqual([])
  })

  it('0 critical/serious на error-состоянии (404)', async () => {
    getReviewQueueItemMock.mockRejectedValue(new ApiError(404, 'not found'))
    const { container } = renderPage('superuser')
    await screen.findByText('Участник не найден.')
    expect(criticalOrSerious(await runAxe(container))).toEqual([])
  })

  it('fe-3.5 AC-3: 0 critical/serious при открытом ReturnReasonDialog', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    const { container } = renderPage('superuser')
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    fireEvent.click(screen.getByTestId('action-return'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(criticalOrSerious(await runAxe(container))).toEqual([])
  })
})
