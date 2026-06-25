import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

const getAttendeesMock = vi.fn()
vi.mock('@/api/attendees', () => ({
  getAttendees: (...a: unknown[]) => getAttendeesMock(...a),
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateMock }
})

import { AttendeesPage } from './AttendeesPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AttendeesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

interface Row {
  id: number
  surname: string
  firstname: string
  patronymic: string | null
  status: string
  category: number | null
  dateAdd: string
  iin_masked: string
}

function page(results: Row[], count: number, extra: Record<string, unknown> = {}) {
  return { count, next: null, previous: null, results, ...extra }
}

const ROW: Row = {
  id: 1,
  surname: 'Иванов',
  firstname: 'Иван',
  patronymic: 'Иванович',
  status: 'draft',
  category: null,
  dateAdd: '2026-06-01T10:00:00Z',
  iin_masked: '********1234',
}

beforeEach(() => {
  getAttendeesMock.mockReset()
  navigateMock.mockReset()
})

describe('AttendeesPage (Story 5.5)', () => {
  it('AC-1: строки с маскированным ИИН + «Показано X–Y из N»', async () => {
    getAttendeesMock.mockResolvedValue(page([ROW], 1))
    renderPage()
    await waitFor(() =>
      expect(screen.getByText('Иванов Иван Иванович')).toBeInTheDocument(),
    )
    expect(screen.getByText('********1234')).toBeInTheDocument()
    expect(screen.getByText(/Показано 1–1 из 1/)).toBeInTheDocument()
  })

  it('AC-2: поиск 3+ символов (debounce) → getAttendees c search', async () => {
    getAttendeesMock.mockResolvedValue(page([], 0))
    renderPage()
    await waitFor(() => expect(getAttendeesMock).toHaveBeenCalled())
    const input = screen.getByLabelText('Поиск по ФИО')
    fireEvent.change(input, { target: { value: 'Ив' } }) // 2 симв — не ищем
    fireEvent.change(input, { target: { value: 'Иванов' } })
    await waitFor(() =>
      expect(
        getAttendeesMock.mock.calls.some(
          (c) => (c[0] as { search?: string }).search === 'Иванов',
        ),
      ).toBe(true),
    )
    expect(
      getAttendeesMock.mock.calls.some(
        (c) => (c[0] as { search?: string }).search === 'Ив',
      ),
    ).toBe(false)
  })

  it('AC-3: фильтр по статусу → getAttendees c status', async () => {
    getAttendeesMock.mockResolvedValue(page([], 0))
    renderPage()
    await waitFor(() => expect(getAttendeesMock).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Фильтр по статусу'), {
      target: { value: 'ready' },
    })
    await waitFor(() =>
      expect(
        getAttendeesMock.mock.calls.some(
          (c) => (c[0] as { status?: string }).status === 'ready',
        ),
      ).toBe(true),
    )
  })

  it('AC-4: пагинация «Вперёд» → page=2', async () => {
    getAttendeesMock.mockResolvedValue(page([ROW], 120, { next: 'http://x/?page=2' }))
    renderPage()
    await waitFor(() =>
      expect(screen.getByText(/Показано 1–50 из 120/)).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Вперёд' }))
    await waitFor(() =>
      expect(
        getAttendeesMock.mock.calls.some((c) => (c[0] as { page?: number }).page === 2),
      ).toBe(true),
    )
  })

  it('AC-5: клик по строке → navigate /attendees/:id', async () => {
    getAttendeesMock.mockResolvedValue(page([ROW], 1))
    renderPage()
    await waitFor(() =>
      expect(screen.getByText('Иванов Иван Иванович')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByText('Иванов Иван Иванович'))
    expect(navigateMock).toHaveBeenCalledWith('/attendees/1')
  })

  it('AC-1: skeleton при первой загрузке', async () => {
    let resolve: (v: unknown) => void = () => {}
    getAttendeesMock.mockReturnValue(
      new Promise((r) => {
        resolve = r
      }),
    )
    renderPage()
    expect(screen.getByLabelText('Загрузка списка')).toBeInTheDocument()
    await act(async () => {
      resolve(page([ROW], 1))
    })
  })
})
