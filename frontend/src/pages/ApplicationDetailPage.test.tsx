import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ApiError } from '@/api/client'
import type { ReviewQueueDetail } from '@/api/reviewQueue.schema'

const getReviewQueueItemMock = vi.fn()
const approveReviewQueueItemMock = vi.fn()
const returnReviewQueueItemMock = vi.fn()
vi.mock('@/api/reviewQueue', () => ({
  getReviewQueueItem: (...a: unknown[]) => getReviewQueueItemMock(...a),
  approveReviewQueueItem: (...a: unknown[]) => approveReviewQueueItemMock(...a),
  returnReviewQueueItem: (...a: unknown[]) => returnReviewQueueItemMock(...a),
}))

const useRoleMock = vi.fn()
vi.mock('@/hooks/useRole', () => ({ useRole: () => useRoleMock() }))

const redirectToLoginMock = vi.fn()
vi.mock('@/lib/auth', () => ({ redirectToLogin: () => redirectToLoginMock() }))

const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('sonner', () => ({
  toast: {
    success: (...a: unknown[]) => toastSuccess(...a),
    error: (...a: unknown[]) => toastError(...a),
  },
}))

import { ApplicationDetailPage } from './ApplicationDetailPage'

function detail(over: Partial<ReviewQueueDetail> = {}): ReviewQueueDetail {
  return {
    id: 101,
    full_name: 'Алиев Бахыт Серикулы',
    iin_masked: '********1234',
    status: 'in_review',
    sub_event_id: 5,
    sub_event_name: 'Пресс-центр',
    problem_flags: [],
    last_return_reason: null,
    return_count: 0,
    photo: '/media/event_5/attendee_photos/sample.jpg',
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

function renderPage(initialEntries: string[] = ['/queue/101'], role: string | undefined = 'superuser') {
  useRoleMock.mockReturnValue(role)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/queue/:id" element={<ApplicationDetailPage />} />
          <Route path="/queue" element={<div>QUEUE-LANDING</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getReviewQueueItemMock.mockReset()
  approveReviewQueueItemMock.mockReset()
  returnReviewQueueItemMock.mockReset()
  useRoleMock.mockReset()
  redirectToLoginMock.mockReset()
  toastSuccess.mockReset()
  toastError.mockReset()
})

describe('ApplicationDetailPage (fe-3.3)', () => {
  it('AC-5: рендерит ФИО, маск-ИИН (verbatim + SR-метка), статус-бейдж, поля', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })).toBeInTheDocument()
    expect(screen.getByText('********1234')).toBeInTheDocument()
    // SR-метка читает последние 4 цифры, не глифы.
    expect(screen.getByText('ИИН, последние четыре цифры 1234')).toBeInTheDocument()
    // StatusBadge присутствует (dot — носитель смысла помимо цвета).
    expect(screen.getByTestId('status-dot')).toBeInTheDocument()
    // Дата рождения ДД.ММ.ГГГГ; резидентство; транслитерация lang="en".
    expect(screen.getByText('05.12.1985')).toBeInTheDocument()
    expect(screen.getByText('Резидент РК')).toBeInTheDocument()
    const translit = screen.getByText('Aliyev Bakhyt Serikuly')
    expect(translit).toHaveAttribute('lang', 'en')
  })

  it('AC-5: сырого 12-значного ИИН нет в DOM', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    const { container } = renderPage()
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    expect((container.textContent ?? '').match(/\d{12}/)).toBeNull()
  })

  it('AC-4: фото 3×4 и скан документа — read-only <img> с alt', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage()
    const photo = await screen.findByAltText('Фото участника')
    expect(photo).toHaveAttribute('src', '/media/event_5/attendee_photos/sample.jpg')
    expect(screen.getByAltText('Скан документа')).toBeInTheDocument()
  })

  it('AC-4: отсутствующее медиа → явный placeholder (не битый <img>)', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail({ photo: null, doc_scan: null }))
    renderPage()
    expect(await screen.findByRole('img', { name: 'Фото отсутствует' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Скан документа отсутствует' })).toBeInTheDocument()
    expect(screen.queryByAltText('Фото участника')).not.toBeInTheDocument()
  })

  it('AC-7: проблемы → конкретные локализованные причины (не «ошибка»)', async () => {
    getReviewQueueItemMock.mockResolvedValue(
      detail({ problem_flags: ['no_photo', 'doc_unreadable'] }),
    )
    renderPage()
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    const problems = screen.getByRole('list', { name: 'Проблемы заявки' })
    expect(problems).toHaveTextContent('Нет фото')
    expect(problems).toHaveTextContent('Документ нечитаем')
  })

  it('AC-6: история возвратов скрыта при return_count=0', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail({ return_count: 0 }))
    renderPage()
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    expect(screen.queryByText(/Возвращалась раз/)).not.toBeInTheDocument()
  })

  it('AC-6: история возвратов видна при return_count>0 + причина', async () => {
    getReviewQueueItemMock.mockResolvedValue(
      detail({ return_count: 2, last_return_reason: 'Нет фото' }),
    )
    renderPage()
    expect(await screen.findByText('Возвращалась раз: 2')).toBeInTheDocument()
    expect(screen.getByText('Последняя причина возврата: Нет фото')).toBeInTheDocument()
  })

  it('AC-8: админ (superuser) → кликабельный breadcrumb, без статичного контекста', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage(['/queue/101'], 'superuser')
    const crumb = await screen.findByRole('link', { name: 'Очередь проверки' })
    expect(crumb).toHaveAttribute('href', '/queue')
    expect(screen.queryByText(/^Заявка · /)).not.toBeInTheDocument()
  })

  it('AC-8: супероператор → тоже breadcrumb', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage(['/queue/101'], 'superoperator')
    expect(await screen.findByRole('link', { name: 'Очередь проверки' })).toBeInTheDocument()
  })

  it('AC-8: оператор → НЕ псевдо-крошки, а статичный нефокусируемый контекст', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage(['/queue/101'], 'operator')
    expect(await screen.findByText('Заявка · Алиев Бахыт Серикулы')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Очередь проверки' })).not.toBeInTheDocument()
  })

  it('fe-3.5 AC-4: для in_review «Одобрить» и «Вернуть с причиной» обе активны', async () => {
    // fe-3.4 включил approve-stub; fe-3.5 включает return-stub (открывает ReturnReasonDialog).
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage()
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    const approve = screen.getByTestId('action-approve')
    const ret = screen.getByTestId('action-return')
    expect(approve).toBeEnabled()
    expect(ret).toBeEnabled()
    expect(approve).toHaveTextContent('Одобрить')
    expect(ret).toHaveTextContent('Вернуть с причиной')
  })

  it('review P1: статус ≠ in_review (submitted) → «Одобрить» disabled (FSM-guard)', async () => {
    // submitted→ready запрещён FSM → approve дал бы 409; кнопка не предлагает падающее действие.
    getReviewQueueItemMock.mockResolvedValue(detail({ status: 'submitted' }))
    renderPage()
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    expect(screen.getByTestId('action-approve')).toBeDisabled()
  })

  it('AC-9: seam ?action=return → кнопка «Вернуть» подсвечена', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage(['/queue/101?action=return'])
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    expect(screen.getByTestId('action-return').className).toContain('ring-2')
  })

  it('AC-3: невалидный id → сообщение, запрос НЕ уходит', async () => {
    renderPage(['/queue/abc'])
    expect(await screen.findByText('Некорректный идентификатор участника.')).toBeInTheDocument()
    expect(getReviewQueueItemMock).not.toHaveBeenCalled()
  })

  it('AC-10: 404 → «Участник не найден.»', async () => {
    getReviewQueueItemMock.mockRejectedValue(new ApiError(404, 'not found'))
    renderPage()
    expect(await screen.findByText('Участник не найден.')).toBeInTheDocument()
  })

  it('AC-10: 403 → «Нет доступа к очереди проверки.»', async () => {
    getReviewQueueItemMock.mockRejectedValue(new ApiError(403, 'forbidden'))
    renderPage()
    expect(await screen.findByText('Нет доступа к очереди проверки.')).toBeInTheDocument()
  })

  it('AC-10: 401 → redirectToLogin()', async () => {
    getReviewQueueItemMock.mockRejectedValue(new ApiError(401, 'unauth'))
    renderPage()
    await waitFor(() => expect(redirectToLoginMock).toHaveBeenCalled())
  })
})

describe('ApplicationDetailPage approve (fe-3.4)', () => {
  it('AC-3: «Одобрить» → approveReviewQueueItem(id) + toast + навигация назад в /queue', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    approveReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'ready' })
    renderPage()
    fireEvent.click(await screen.findByTestId('action-approve'))
    await waitFor(() => expect(approveReviewQueueItemMock).toHaveBeenCalledWith(101))
    // Заявка покинула очередь → уводим в /queue (route рендерит QUEUE-LANDING).
    expect(await screen.findByText('QUEUE-LANDING')).toBeInTheDocument()
    expect(toastSuccess).toHaveBeenCalledWith('Заявка одобрена')
  })

  it('AC-3: во время запроса кнопка disabled (без двойного клика)', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    let resolve: (v: { id: number; status: string }) => void = () => {}
    approveReviewQueueItemMock.mockReturnValue(
      new Promise((r) => {
        resolve = r
      }),
    )
    renderPage()
    const approve = await screen.findByTestId('action-approve')
    fireEvent.click(approve)
    await waitFor(() => expect(approve).toBeDisabled())
    resolve({ id: 101, status: 'ready' })
    // review P10 — дожидаемся пост-success эффектов (navigate/toast/invalidate), иначе
    // обновления состояния идут вне act() → предупреждения и протечка состояния в соседние тесты.
    expect(await screen.findByText('QUEUE-LANDING')).toBeInTheDocument()
  })

  it('AC-3/AC-5: 409 → toast с локализованным машинным кодом (не «сеть», без навигации)', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    approveReviewQueueItemMock.mockRejectedValue(
      new ApiError(409, 'conflict', { type: 'status_transition_invalid', field: 'status' }),
    )
    renderPage()
    fireEvent.click(await screen.findByTestId('action-approve'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('Недопустимый переход статуса.'))
    // НЕ навигировали (заявка не одобрена) — заголовок детали ещё на месте.
    expect(screen.getByRole('heading', { name: 'Алиев Бахыт Серикулы' })).toBeInTheDocument()
    expect(screen.queryByText('QUEUE-LANDING')).not.toBeInTheDocument()
  })

  it('AC-3: сетевая ошибка (не ApiError) → общий network_error toast', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    approveReviewQueueItemMock.mockRejectedValue(new Error('boom'))
    renderPage()
    fireEvent.click(await screen.findByTestId('action-approve'))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('Сеть недоступна. Повторите.'))
  })
})

describe('ApplicationDetailPage return (fe-3.5)', () => {
  it('AC-4: статус ≠ in_review (submitted) → «Вернуть с причиной» disabled (FSM-guard)', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail({ status: 'submitted' }))
    renderPage()
    await screen.findByRole('heading', { name: 'Алиев Бахыт Серикулы' })
    expect(screen.getByTestId('action-return')).toBeDisabled()
  })

  it('AC-3: «Вернуть» открывает ReturnReasonDialog; submit disabled пока причина пуста', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage()
    fireEvent.click(await screen.findByTestId('action-return'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    const submit = screen.getByRole('button', { name: 'Подтвердить возврат' })
    expect(submit).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Причина возврата'), { target: { value: 'Нет фото' } })
    expect(submit).toBeEnabled()
  })

  it('AC-9: seam ?action=return → диалог авто-открывается', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage(['/queue/101?action=return'])
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('AC-6: submit → toast с «Отменить»; POST отложен (не вызван сразу)', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    returnReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'submitted' })
    renderPage()
    fireEvent.click(await screen.findByTestId('action-return'))
    fireEvent.change(screen.getByLabelText('Причина возврата'), { target: { value: 'Нет фото' } })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить возврат' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const opts = toastSuccess.mock.calls.at(-1)![1] as { action?: { label: string } }
    expect(opts.action?.label).toBe('Отменить')
    expect(returnReviewQueueItemMock).not.toHaveBeenCalled()
  })

  it('AC-6: «Отменить» отменяет возврат (кнопка снова активна, POST не уходит)', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    renderPage()
    fireEvent.click(await screen.findByTestId('action-return'))
    fireEvent.change(screen.getByLabelText('Причина возврата'), { target: { value: 'Нет фото' } })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить возврат' }))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled())
    // В окне undo возврат «в полёте» → кнопка «Вернуть» disabled (наблюдаемое pending-состояние).
    expect(screen.getByTestId('action-return')).toBeDisabled()
    const undo = (toastSuccess.mock.calls.at(-1)![1] as { action: { onClick: () => void } }).action.onClick
    act(() => undo())
    // undo сбросил pending → кнопка снова активна: НАБЛЮДАЕМЫЙ эффект отмены (не тавтология —
    // no-op undo оставил бы кнопку disabled), и отложенный POST так и не ушёл.
    await waitFor(() => expect(screen.getByTestId('action-return')).toBeEnabled())
    expect(returnReviewQueueItemMock).not.toHaveBeenCalled()
  })

  it('AC-4: по истечении окна → returnReviewQueueItem(id, reason) + навигация в /queue', async () => {
    getReviewQueueItemMock.mockResolvedValue(detail())
    returnReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'submitted' })
    renderPage()
    fireEvent.click(await screen.findByTestId('action-return'))
    fireEvent.change(screen.getByLabelText('Причина возврата'), { target: { value: 'Нет фото' } })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить возврат' }))
    await waitFor(() => expect(returnReviewQueueItemMock).toHaveBeenCalledWith(101, 'Нет фото'), {
      timeout: 4000,
    })
    expect(await screen.findByText('QUEUE-LANDING')).toBeInTheDocument()
  })
})
