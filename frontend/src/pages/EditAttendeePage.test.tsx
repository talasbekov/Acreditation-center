import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const getAttendeeMock = vi.fn()
const submitAttendeeMock = vi.fn()
vi.mock('@/api/attendees', () => ({
  getAttendee: (...a: unknown[]) => getAttendeeMock(...a),
  submitAttendee: (...a: unknown[]) => submitAttendeeMock(...a),
  getAttendees: vi.fn(),
}))

// Этап D: форма загружает список заявок и в правке — показать название, а не «#id».
vi.mock('@/api/requests', () => ({
  getRequests: () => Promise.resolve([{ id: 1, name: 'A-01', event_id: 1, event_name: 'Форум' }]),
}))

vi.mock('@/api/directories', () => ({
  getDirectories: () => Promise.resolve({ sexes: [], document_types: [], categories: [], countries: [{ code: '1000000105', name: 'Казахстан' }] }),
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
  submitAttendeeMock.mockReset()
  redirectToLoginMock.mockReset()
})

describe('EditAttendeePage — статус и отправка (этап C)', () => {
  it('возвращённый черновик: подпись, причина и кнопка отправки', async () => {
    getAttendeeMock.mockResolvedValue({ ...DETAIL, review_comment: 'Скан нечитаем' })
    renderEdit()
    await waitFor(() =>
      expect(screen.getByText('Возвращён на доработку')).toBeInTheDocument(),
    )
    expect(screen.getByRole('note')).toHaveTextContent('Причина возврата: Скан нечитаем')
    expect(screen.getByRole('button', { name: 'Отправить на проверку' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Сохранить изменения' })).toBeInTheDocument()
  })

  it('обычный черновик: без причины', async () => {
    getAttendeeMock.mockResolvedValue({ ...DETAIL, review_comment: '' })
    renderEdit()
    await waitFor(() => expect(screen.getByText('Черновик')).toBeInTheDocument())
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })

  it('отправка: POST submit, затем статус и блокировка формы', async () => {
    getAttendeeMock.mockResolvedValue(DETAIL)
    submitAttendeeMock.mockResolvedValue({ ...DETAIL, status: 'submitted' })
    renderEdit()
    const button = await screen.findByRole('button', { name: 'Отправить на проверку' })
    fireEvent.click(button)
    await waitFor(() =>
      expect(screen.getByText('Отправлен на проверку')).toBeInTheDocument(),
    )
    expect(submitAttendeeMock).toHaveBeenCalledWith(5)
    expect(screen.getByText('Редактирование заблокировано')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Отправить|Сохранить/ })).not.toBeInTheDocument()
  })

  it('отказ сервера: понятный текст без служебного префикса', async () => {
    getAttendeeMock.mockResolvedValue(DETAIL)
    submitAttendeeMock.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        title: 'Bad Request',
        detail: 'status: Участник не готов к отправке: нет фото',
        field: 'status',
      }),
    )
    renderEdit()
    fireEvent.click(await screen.findByRole('button', { name: 'Отправить на проверку' }))
    await waitFor(() =>
      expect(screen.getByText('Участник не готов к отправке: нет фото')).toBeInTheDocument(),
    )
    expect(screen.getByText('Черновик')).toBeInTheDocument()
  })

  it('отправленный участник: только просмотр, без кнопки отправки', async () => {
    getAttendeeMock.mockResolvedValue({ ...DETAIL, status: 'submitted' })
    renderEdit()
    await waitFor(() =>
      expect(screen.getByText('Редактирование заблокировано')).toBeInTheDocument(),
    )
    expect(screen.getByText('Отправлен на проверку')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Отправить на проверку' })).not.toBeInTheDocument()
  })
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
    // Этап D: заблокированное поле заявки показывает название, а не «Заявка #1».
    expect(await screen.findByDisplayValue('A-01 — Форум')).toBeDisabled()
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
