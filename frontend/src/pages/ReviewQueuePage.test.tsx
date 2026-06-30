import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ApiError } from '@/api/client'
import type { ReviewQueueItem, PaginatedReviewQueue } from '@/api/reviewQueue.schema'

const getReviewQueueMock = vi.fn()
const approveReviewQueueItemMock = vi.fn()
const returnReviewQueueItemMock = vi.fn()
vi.mock('@/api/reviewQueue', () => ({
  getReviewQueue: (...a: unknown[]) => getReviewQueueMock(...a),
  approveReviewQueueItem: (...a: unknown[]) => approveReviewQueueItemMock(...a),
  returnReviewQueueItem: (...a: unknown[]) => returnReviewQueueItemMock(...a),
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigateMock }
})

const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('sonner', () => ({
  toast: {
    success: (...a: unknown[]) => toastSuccess(...a),
    error: (...a: unknown[]) => toastError(...a),
  },
}))

/** Управляет prefers-reduced-motion для теста (jsdom не реализует matchMedia). */
function setReducedMotion(reduce: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: reduce,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia
}

import { ReviewQueuePage } from './ReviewQueuePage'

function row(over: Partial<ReviewQueueItem> = {}): ReviewQueueItem {
  return {
    id: 101,
    full_name: 'Алиев Бахыт Серикулы',
    iin_masked: '********1234',
    status: 'submitted',
    sub_event_id: 5,
    sub_event_name: 'Пресс-центр',
    problem_flags: [],
    last_return_reason: null,
    return_count: 0,
    ...over,
  }
}

function envelope(results: ReviewQueueItem[], count: number, extra: Partial<PaginatedReviewQueue> = {}): PaginatedReviewQueue {
  return { count, next: null, previous: null, results, ...extra }
}

function renderPage(initialEntries: string[] = ['/queue']) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initialEntries}>
        <ReviewQueuePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getReviewQueueMock.mockReset()
  approveReviewQueueItemMock.mockReset()
  returnReviewQueueItemMock.mockReset()
  navigateMock.mockReset()
  toastSuccess.mockReset()
  toastError.mockReset()
  setReducedMotion(false) // дефолт — анимация; reduced-тесты переопределяют
})

describe('ReviewQueuePage (fe-3.2)', () => {
  it('AC-1: колонки + строка (ФИО/маск-ИИН/под-событие/статус-бейдж)', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([row()], 1))
    renderPage()
    // Скоупим в строку: метки статуса/проблем дублируются в фильтр-<option> (вне таблицы).
    const tr = (await screen.findByText('Алиев Бахыт Серикулы')).closest('tr')!
    const cell = within(tr)
    expect(cell.getByText('********1234')).toBeInTheDocument()
    expect(cell.getByText('Пресс-центр')).toBeInTheDocument()
    expect(cell.getByText('Отправлен')).toBeInTheDocument() // StatusBadge: submitted → «Отправлен»
    expect(screen.getByRole('columnheader', { name: 'ФИО' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Под-событие' })).toBeInTheDocument()
  })

  it('AC-1: sub_event_name=null → «—»', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([row({ id: 103, sub_event_id: null, sub_event_name: null })], 1))
    renderPage()
    await waitFor(() => expect(screen.getByText('Алиев Бахыт Серикулы')).toBeInTheDocument())
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('AC-1: флаг-строка получает tint-класс + локализованную причину', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([row({ problem_flags: ['no_photo'] })], 1))
    renderPage()
    const tr = (await screen.findByText('Алиев Бахыт Серикулы')).closest('tr')!
    expect(tr.className).toContain('bg-status-rejected-tint')
    expect(tr.className).toContain('border-l-[3px]') // левая полоса-индикатор (P10)
    expect(tr.className).toContain('border-status-rejected')
    expect(within(tr).getByText('Нет фото')).toBeInTheDocument()
  })

  it('AC-1: «Проверить» — ссылка на detail-route /queue/:id', async () => {
    // fe-3.5: «Вернуть» теперь кнопка (инлайн-диалог), а не Link на ?action=return — см. row-return.
    getReviewQueueMock.mockResolvedValue(envelope([row({ id: 101 })], 1))
    renderPage()
    const review = await screen.findByRole('link', { name: 'Проверить' })
    expect(review).toHaveAttribute('href', '/queue/101')
  })

  it('AC-3: пустое «Всё проверено» когда нет фильтров', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([], 0))
    renderPage()
    await waitFor(() => expect(screen.getByText('Всё проверено')).toBeInTheDocument())
  })

  it('AC-3: пустое «не найдено» когда активен фильтр', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([], 0))
    renderPage(['/queue?status=in_review'])
    await waitFor(() =>
      expect(screen.getByText('По заданным фильтрам ничего не найдено.')).toBeInTheDocument(),
    )
    expect(screen.queryByText('Всё проверено')).not.toBeInTheDocument()
  })

  it('AC-2: фильтр статуса (URL-state) → getReviewQueue c status', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([], 0))
    renderPage()
    await waitFor(() => expect(getReviewQueueMock).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('Фильтр по статусу'), { target: { value: 'in_review' } })
    await waitFor(() =>
      expect(
        getReviewQueueMock.mock.calls.some((c) => (c[0] as { status?: string }).status === 'in_review'),
      ).toBe(true),
    )
  })

  it('AC-2: URL-state восстанавливается (?status=… на старте)', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([], 0))
    renderPage(['/queue?status=submitted'])
    await waitFor(() => expect(getReviewQueueMock).toHaveBeenCalled())
    expect((getReviewQueueMock.mock.calls[0][0] as { status?: string }).status).toBe('submitted')
    expect((screen.getByLabelText('Фильтр по статусу') as HTMLSelectElement).value).toBe('submitted')
  })

  it('AC-2: поиск <3 символов после ОТРАБОТКИ debounce НЕ уходит на сервер (gate реально покрыт)', async () => {
    // P9 (review): прежний тест печатал «Ал»→«Алиев» синхронно — таймер «Ал» гасился
    // коалесингом, поэтому ассерт прошёл бы даже без min-3-гейта. Здесь даём «Ал»-debounce
    // отработать (400мс > 300мс) и проверяем, что НИ один запрос не ушёл с search.
    getReviewQueueMock.mockResolvedValue(envelope([], 0))
    renderPage()
    await waitFor(() => expect(getReviewQueueMock).toHaveBeenCalled())
    const input = screen.getByLabelText('Поиск по ФИО')
    fireEvent.change(input, { target: { value: 'Ал' } })
    await new Promise((r) => setTimeout(r, 400))
    expect(getReviewQueueMock.mock.calls.some((c) => (c[0] as { search?: string }).search)).toBe(false)
    // 3+ символа — уходит
    fireEvent.change(input, { target: { value: 'Алиев' } })
    await waitFor(() =>
      expect(getReviewQueueMock.mock.calls.some((c) => (c[0] as { search?: string }).search === 'Алиев')).toBe(true),
    )
  })

  it('AC-2 (review P2/P3): невалидный deep-link status НЕ уходит на бэкенд и не ломает select', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([], 0))
    renderPage(['/queue?status=ready']) // ready вне очереди → backend 400; должен быть санитизирован в ''
    await waitFor(() => expect(getReviewQueueMock).toHaveBeenCalled())
    expect((getReviewQueueMock.mock.calls[0][0] as { status?: string }).status).toBeUndefined()
    expect((screen.getByLabelText('Фильтр по статусу') as HTMLSelectElement).value).toBe('')
    // невалидный фильтр санитизирован → пустая очередь = «всё проверено», не «не найдено»
    expect(await screen.findByText('Всё проверено')).toBeInTheDocument()
    expect(screen.queryByText('По заданным фильтрам ничего не найдено.')).not.toBeInTheDocument()
  })

  it('AC-2: пагинация «Вперёд» → page=2', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([row()], 120, { next: 'http://x/?page=2' }))
    renderPage()
    await waitFor(() => expect(screen.getByText(/Показано 1–50 из 120/)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Вперёд' }))
    await waitFor(() =>
      expect(getReviewQueueMock.mock.calls.some((c) => (c[0] as { page?: number }).page === 2)).toBe(true),
    )
  })

  it('AC-2 (review P1): out-of-range page → 404 → восстановление на стр.1, без тупика', async () => {
    getReviewQueueMock.mockImplementation((p: { page?: number }) =>
      p?.page === 3
        ? Promise.reject(new ApiError(404, 'not found'))
        : Promise.resolve(envelope([row()], 1)),
    )
    renderPage(['/queue?page=3'])
    await waitFor(() =>
      expect(getReviewQueueMock.mock.calls.some((c) => (c[0] as { page?: number }).page === 1)).toBe(true),
    )
    await waitFor(() => expect(screen.getByText('Алиев Бахыт Серикулы')).toBeInTheDocument())
    expect(screen.queryByText('Не удалось загрузить очередь проверки.')).not.toBeInTheDocument()
  })

  it('AC-2: skeleton при первой загрузке', () => {
    getReviewQueueMock.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.getByLabelText('Загрузка очереди')).toBeInTheDocument()
  })

  it('AC-6: 403 → «нет доступа» (не общий load_error)', async () => {
    getReviewQueueMock.mockRejectedValue(new ApiError(403, 'forbidden'))
    renderPage()
    await waitFor(() => expect(screen.getByText('Нет доступа к очереди проверки.')).toBeInTheDocument())
    expect(screen.queryByText('Не удалось загрузить очередь проверки.')).not.toBeInTheDocument()
  })

  it('AC-6: прочая ошибка → общий load_error', async () => {
    getReviewQueueMock.mockRejectedValue(new ApiError(500, 'boom'))
    renderPage()
    await waitFor(() => expect(screen.getByText('Не удалось загрузить очередь проверки.')).toBeInTheDocument())
  })

  it('AC-4: клик по строке → navigate /queue/:id', async () => {
    getReviewQueueMock.mockResolvedValue(envelope([row({ id: 101 })], 1))
    renderPage()
    const cell = await screen.findByText('Алиев Бахыт Серикулы')
    fireEvent.click(cell.closest('tr')!)
    expect(navigateMock).toHaveBeenCalledWith('/queue/101')
  })

  it('AC-1: все 5 enum-флагов представимы (legacy/backfill строка)', async () => {
    getReviewQueueMock.mockResolvedValue(
      envelope([row({ id: 103, problem_flags: ['no_photo', 'doc_unreadable', 'photo_ratio', 'duplicate_attendee', 'iin_invalid'] })], 1),
    )
    renderPage()
    const tr = (await screen.findByText('Алиев Бахыт Серикулы')).closest('tr')!
    const cell = within(tr)
    expect(cell.getByText('Нет фото')).toBeInTheDocument()
    expect(cell.getByText('Документ нечитаем')).toBeInTheDocument()
    expect(cell.getByText('Фото: неверные пропорции')).toBeInTheDocument() // P8: 5-й флаг photo_ratio
    expect(cell.getByText('Возможный дубликат')).toBeInTheDocument()
    expect(cell.getByText('ИИН: ошибка')).toBeInTheDocument()
  })
})

describe('ReviewQueuePage row-approve (fe-3.4 AC-4)', () => {
  function pair() {
    // review P1 — approve-кнопка теперь только для in_review (submitted→ready запрещён FSM).
    return [
      row({ id: 101, full_name: 'Алиев Бахыт', status: 'in_review' }),
      row({ id: 102, full_name: 'Иванова Мария', status: 'in_review' }),
    ]
  }

  it('одобрение из строки → approveReviewQueueItem(id) + toast.success, БЕЗ навигации в detail', async () => {
    setReducedMotion(true)
    getReviewQueueMock.mockResolvedValue(envelope(pair(), 2))
    approveReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'ready' })
    renderPage()
    const tr = (await screen.findByText('Алиев Бахыт')).closest('tr')!
    fireEvent.click(within(tr).getByRole('button', { name: 'Одобрить' }))
    await waitFor(() => expect(approveReviewQueueItemMock).toHaveBeenCalledWith(101))
    expect(toastSuccess).toHaveBeenCalledWith('Заявка одобрена')
    // stopPropagation: клик по кнопке НЕ открывает detail-route строки.
    expect(navigateMock).not.toHaveBeenCalledWith('/queue/101')
  })

  it('reduced-motion: фокус приземляется на СОСЕДНЮЮ строку + ре-фетч (сервер-истина)', async () => {
    setReducedMotion(true)
    getReviewQueueMock
      .mockResolvedValueOnce(envelope(pair(), 2))
      .mockResolvedValue(envelope([row({ id: 102, full_name: 'Иванова Мария' })], 1))
    approveReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'ready' })
    renderPage()
    const tr1 = (await screen.findByText('Алиев Бахыт')).closest('tr')!
    fireEvent.click(within(tr1).getByRole('button', { name: 'Одобрить' }))
    // После ре-фетча одобренная строка ушла; соседняя (Иванова) держит фокус.
    await waitFor(() => expect(screen.queryByText('Алиев Бахыт')).not.toBeInTheDocument())
    const tr2 = screen.getByText('Иванова Мария').closest('tr')!
    expect(document.activeElement).toBe(tr2)
    expect(getReviewQueueMock.mock.calls.length).toBeGreaterThanOrEqual(2) // был ре-фетч
  })

  it('reduced-motion: очередь опустела → фокус в поле поиска (не в body)', async () => {
    setReducedMotion(true)
    getReviewQueueMock
      .mockResolvedValueOnce(envelope([row({ id: 101, full_name: 'Алиев Бахыт', status: 'in_review' })], 1))
      .mockResolvedValue(envelope([], 0))
    approveReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'ready' })
    renderPage()
    const tr = (await screen.findByText('Алиев Бахыт')).closest('tr')!
    fireEvent.click(within(tr).getByRole('button', { name: 'Одобрить' }))
    await waitFor(() => expect(screen.getByText('Всё проверено')).toBeInTheDocument())
    expect(document.activeElement).toBe(screen.getByLabelText('Поиск по ФИО'))
    expect(document.activeElement).not.toBe(document.body)
  })

  it('motion-safe: одобряемая строка получает тающие классы (анимация)', async () => {
    setReducedMotion(false)
    getReviewQueueMock.mockResolvedValue(envelope(pair(), 2)) // ре-фетч возвращает те же → класс снимется
    approveReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'ready' })
    renderPage()
    const tr = (await screen.findByText('Алиев Бахыт')).closest('tr')!
    fireEvent.click(within(tr).getByRole('button', { name: 'Одобрить' }))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled())
    expect(tr.className).toContain('motion-safe:opacity-0')
    expect(tr.className).toContain('pointer-events-none')
    // После FADE_MS (300мс) + ре-фетча тающий класс снимается (approvingId=null).
    await waitFor(() => expect(tr.className).not.toContain('motion-safe:opacity-0'))
  })

  it('409 при одобрении из строки → toast.error (машинный код), строка НЕ тает', async () => {
    setReducedMotion(true)
    getReviewQueueMock.mockResolvedValue(envelope(pair(), 2))
    approveReviewQueueItemMock.mockRejectedValue(
      new ApiError(409, 'conflict', { type: 'status_transition_invalid', field: 'status' }),
    )
    renderPage()
    const tr = (await screen.findByText('Алиев Бахыт')).closest('tr')!
    fireEvent.click(within(tr).getByRole('button', { name: 'Одобрить' }))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('Недопустимый переход статуса.'))
    expect(screen.getByText('Алиев Бахыт')).toBeInTheDocument()
    expect(tr.className).not.toContain('motion-safe:opacity-0')
  })

  it('review P1: approve-кнопка только для in_review (submitted → кнопки нет)', async () => {
    getReviewQueueMock.mockResolvedValue(
      envelope(
        [
          row({ id: 101, full_name: 'Сабмит', status: 'submitted' }),
          row({ id: 102, full_name: 'Ревью', status: 'in_review' }),
        ],
        2,
      ),
    )
    renderPage()
    const trSub = (await screen.findByText('Сабмит')).closest('tr')!
    const trRev = screen.getByText('Ревью').closest('tr')!
    expect(within(trSub).queryByRole('button', { name: 'Одобрить' })).not.toBeInTheDocument()
    expect(within(trRev).getByRole('button', { name: 'Одобрить' })).toBeInTheDocument()
  })

  it('review P5: 409 из строки → ре-фетч очереди (устаревшая строка не зависает)', async () => {
    setReducedMotion(true)
    getReviewQueueMock.mockResolvedValue(envelope(pair(), 2))
    approveReviewQueueItemMock.mockRejectedValue(
      new ApiError(409, 'conflict', { type: 'status_transition_invalid', field: 'status' }),
    )
    renderPage()
    await screen.findByText('Алиев Бахыт')
    const before = getReviewQueueMock.mock.calls.length
    const tr = screen.getByText('Алиев Бахыт').closest('tr')!
    fireEvent.click(within(tr).getByRole('button', { name: 'Одобрить' }))
    await waitFor(() => expect(toastError).toHaveBeenCalled())
    // invalidate → дополнительный fetch (сверх первичного) сводит UI к серверной истине.
    await waitFor(() => expect(getReviewQueueMock.mock.calls.length).toBeGreaterThan(before))
  })

  it('review P9: Enter по тающей (одобряемой) строке не навигирует в detail', async () => {
    setReducedMotion(false) // motion-safe → строка держится в fadingIds на FADE_MS
    getReviewQueueMock.mockResolvedValue(envelope(pair(), 2))
    approveReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'ready' })
    renderPage()
    const tr = (await screen.findByText('Алиев Бахыт')).closest('tr')!
    fireEvent.click(within(tr).getByRole('button', { name: 'Одобрить' }))
    await waitFor(() => expect(tr.className).toContain('motion-safe:opacity-0')) // в fadingIds
    navigateMock.mockClear()
    fireEvent.keyDown(tr, { key: 'Enter' })
    expect(navigateMock).not.toHaveBeenCalledWith('/queue/101')
  })
})

describe('ReviewQueuePage row-return (fe-3.5 AC-5/AC-6)', () => {
  function inReviewPair() {
    return [
      row({ id: 101, full_name: 'Алиев Бахыт', status: 'in_review' }),
      row({ id: 102, full_name: 'Иванова Мария', status: 'in_review' }),
    ]
  }

  function openReturnDialog(name: string) {
    fireEvent.click(within(screen.getByText(name).closest('tr')!).getByRole('button', { name: 'Вернуть' }))
    return screen.getByRole('dialog')
  }

  it('кнопка «Вернуть» только для in_review (submitted → нет кнопки)', async () => {
    getReviewQueueMock.mockResolvedValue(
      envelope(
        [
          row({ id: 101, full_name: 'Сабмит', status: 'submitted' }),
          row({ id: 102, full_name: 'Ревью', status: 'in_review' }),
        ],
        2,
      ),
    )
    renderPage()
    const trSub = (await screen.findByText('Сабмит')).closest('tr')!
    const trRev = screen.getByText('Ревью').closest('tr')!
    expect(within(trSub).queryByRole('button', { name: 'Вернуть' })).not.toBeInTheDocument()
    expect(within(trRev).getByRole('button', { name: 'Вернуть' })).toBeInTheDocument()
  })

  it('диалог: submit disabled пока причина пуста, открывается из строки', async () => {
    getReviewQueueMock.mockResolvedValue(envelope(inReviewPair(), 2))
    renderPage()
    await screen.findByText('Алиев Бахыт')
    openReturnDialog('Алиев Бахыт')
    const submit = screen.getByRole('button', { name: 'Подтвердить возврат' })
    expect(submit).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Причина возврата'), { target: { value: 'Нет фото' } })
    expect(submit).toBeEnabled()
  })

  it('submit → строка тает + toast с «Отменить»; реальный POST отложен (не вызван сразу)', async () => {
    getReviewQueueMock.mockResolvedValue(envelope(inReviewPair(), 2))
    returnReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'submitted' })
    renderPage()
    const tr = (await screen.findByText('Алиев Бахыт')).closest('tr')!
    openReturnDialog('Алиев Бахыт')
    fireEvent.change(screen.getByLabelText('Причина возврата'), { target: { value: 'Нет фото' } })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить возврат' }))
    // диалог закрылся, строка тает
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(tr.className).toContain('motion-safe:opacity-0')
    // toast с action «Отменить»; POST ещё НЕ ушёл (отложен на окно undo)
    const opts = toastSuccess.mock.calls.at(-1)![1] as { action?: { label: string } }
    expect(opts.action?.label).toBe('Отменить')
    expect(returnReviewQueueItemMock).not.toHaveBeenCalled()
  })

  it('«Отменить» → POST не уходит, строка восстановлена', async () => {
    getReviewQueueMock.mockResolvedValue(envelope(inReviewPair(), 2))
    renderPage()
    const tr = (await screen.findByText('Алиев Бахыт')).closest('tr')!
    openReturnDialog('Алиев Бахыт')
    fireEvent.change(screen.getByLabelText('Причина возврата'), { target: { value: 'Нет фото' } })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить возврат' }))
    await waitFor(() => expect(tr.className).toContain('motion-safe:opacity-0'))
    const undo = (toastSuccess.mock.calls.at(-1)![1] as { action: { onClick: () => void } }).action.onClick
    act(() => undo())
    expect(tr.className).not.toContain('motion-safe:opacity-0') // строка восстановлена
    expect(returnReviewQueueItemMock).not.toHaveBeenCalled() // отмена до вызова
  })

  it('по истечении окна → returnReviewQueueItem(id, reason) + ре-фетч', async () => {
    getReviewQueueMock.mockResolvedValue(envelope(inReviewPair(), 2))
    returnReviewQueueItemMock.mockResolvedValue({ id: 101, status: 'submitted' })
    renderPage()
    await screen.findByText('Алиев Бахыт')
    const calls = getReviewQueueMock.mock.calls.length
    openReturnDialog('Алиев Бахыт')
    fireEvent.change(screen.getByLabelText('Причина возврата'), { target: { value: 'Нет фото' } })
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить возврат' }))
    // окно undo ~3с → реальный POST с причиной, затем invalidate
    await waitFor(
      () => expect(returnReviewQueueItemMock).toHaveBeenCalledWith(101, 'Нет фото'),
      { timeout: 4000 },
    )
    await waitFor(() => expect(getReviewQueueMock.mock.calls.length).toBeGreaterThan(calls))
  })
})
