import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const getAttendeeMock = vi.fn()
vi.mock('@/api/attendees', () => ({
  getAttendee: (...a: unknown[]) => getAttendeeMock(...a),
  getAttendees: vi.fn(),
}))

const redirectToLoginMock = vi.fn()
vi.mock('@/lib/auth', () => ({
  redirectToLogin: () => redirectToLoginMock(),
}))

import { ApiError } from '@/api/client'
import { EditAttendeePage } from './EditAttendeePage'

function renderEdit(id = '5') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/attendees/${id}`]}>
        <Routes>
          <Route path="/attendees/:id" element={<EditAttendeePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const DETAIL = {
  id: 5,
  surname: 'Иванов',
  firstname: 'Иван',
  patronymic: 'Иванович',
  birthDate: '1990-05-15',
  countryId: '1000000105',
  iin: '900515312349',
  request: 1,
  status: 'draft',
}

beforeEach(() => {
  getAttendeeMock.mockReset()
  redirectToLoginMock.mockReset()
})

describe('EditAttendeePage (Story 5.5)', () => {
  it('AC-5: предзаполняет форму из detail', async () => {
    getAttendeeMock.mockResolvedValue(DETAIL)
    renderEdit()
    await waitFor(() =>
      expect((screen.getByLabelText('Фамилия') as HTMLInputElement).value).toBe(
        'Иванов',
      ),
    )
    // ИИН: запрашиваем по значению — при валидном ИИН рядом ✅ (aria-label),
    // что ломает getByLabelText('ИИН') exact-match (accessible name загрязняется).
    expect(screen.getByDisplayValue('900515312349')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Сохранить изменения' })).toBeInTheDocument()
  })

  it('AC-5: read-only при статусе ready — баннер + нет кнопки сохранения', async () => {
    getAttendeeMock.mockResolvedValue({ ...DETAIL, status: 'ready' })
    renderEdit()
    await waitFor(() =>
      expect(screen.getByText('Редактирование заблокировано')).toBeInTheDocument(),
    )
    expect(
      screen.queryByRole('button', { name: /Сохранить/ }),
    ).not.toBeInTheDocument()
  })

  // ── P2-2: различаем 401/403/404 detail-загрузки ──────────────────────
  it('P2-2: 404 → «не найден»', async () => {
    getAttendeeMock.mockRejectedValue(new ApiError(404, 'Not Found'))
    renderEdit()
    await waitFor(() =>
      expect(screen.getByText(/не найден/i)).toBeInTheDocument(),
    )
  })

  it('P2-2: 403 → «нет доступа»', async () => {
    getAttendeeMock.mockRejectedValue(new ApiError(403, 'Forbidden'))
    renderEdit()
    await waitFor(() =>
      expect(screen.getByText(/нет доступа/i)).toBeInTheDocument(),
    )
  })

  it('P2-2: 401 (истёкшая сессия) → редирект на логин', async () => {
    getAttendeeMock.mockRejectedValue(new ApiError(401, 'Unauthorized'))
    renderEdit()
    await waitFor(() => expect(redirectToLoginMock).toHaveBeenCalled())
  })

  it('P2-2: прочие ошибки → общее сообщение', async () => {
    getAttendeeMock.mockRejectedValue(new ApiError(500, 'Server Error'))
    renderEdit()
    await waitFor(() =>
      expect(screen.getByText(/Не удалось загрузить участника/i)).toBeInTheDocument(),
    )
  })
})
