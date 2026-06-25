import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const apiFetchMock = vi.fn()
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch: (...args: unknown[]) => apiFetchMock(...args) }
})

const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('sonner', () => ({
  toast: {
    success: (...a: unknown[]) => toastSuccess(...a),
    error: (...a: unknown[]) => toastError(...a),
  },
}))

// FE-1: форма грузит RBAC-scoped список Request для селектора категории.
// Мокаем отдельным модулем (не через apiFetch) → счётчик apiFetch не меняется.
const getRequestsMock = vi.fn()
vi.mock('@/api/requests', () => ({
  getRequests: () => getRequestsMock(),
}))

import { AttendeeForm } from './AttendeeForm'

// FE-1: дефолтный список категорий для всех тестов (id=1 нужен существующим
// кейсам `set(/Категория/, '1')`). Top-level beforeEach → раньше describe-scoped.
beforeEach(() => {
  getRequestsMock.mockReset()
  getRequestsMock.mockResolvedValue([
    { id: 1, name: 'Категория А', event_id: 1, event_name: 'Событие 1' },
    { id: 2, name: 'Категория Б', event_id: 1, event_name: 'Событие 1' },
  ])
})

// Story 5.5: AttendeeForm использует useQueryClient → оборачиваем в провайдер.
function renderForm(ui = <AttendeeForm />) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

function set(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

// Story 5.4: изоляция localStorage между тестами (форма читает черновик на mount).
afterEach(() => {
  localStorage.clear()
})

describe('AttendeeForm (Story 5.2)', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    toastSuccess.mockReset()
    toastError.mockReset()
  })

  it('AC-3: страна ≠ Казахстан → поле ИИН исчезает', async () => {
    renderForm()
    expect(screen.getByLabelText('ИИН')).toBeInTheDocument()
    set('Страна', '643')
    await waitFor(() =>
      expect(screen.queryByLabelText('ИИН')).not.toBeInTheDocument(),
    )
  })

  it('AC-2: резидент + неверная контрольная цифра → inline-ошибка', async () => {
    renderForm()
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312340') // контрольная цифра неверна
    await waitFor(() =>
      expect(screen.getByText(/неверная контрольная цифра/i)).toBeInTheDocument(),
    )
  })

  it('AC-2: несовпадение даты рождения → сообщение с DD.MM.YYYY', async () => {
    renderForm()
    set('Дата рождения', '1990-05-16')
    set('ИИН', '900515312349') // валидный ИИН на 15.05.1990
    await waitFor(() =>
      expect(screen.getByText(/не совпадает с введённой/i)).toBeInTheDocument(),
    )
  })

  it('AC-2 (патч): смена даты ПОСЛЕ валидного ИИН перевалидирует cross-field', async () => {
    renderForm()
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349') // валиден на 15.05.1990 → ошибки нет
    await waitFor(() =>
      expect(screen.queryByText(/не совпадает/i)).not.toBeInTheDocument(),
    )
    set('Дата рождения', '1990-05-16') // теперь не совпадает с ИИН
    await waitFor(() =>
      expect(screen.getByText(/не совпадает с введённой/i)).toBeInTheDocument(),
    )
  })

  it('AC-4: валидная форма → POST /api/v1/attendees/ + toast success', async () => {
    apiFetchMock.mockResolvedValue({ id: 1 })
    renderForm()
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория А/ })
    set(/Категория/, '1')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1))
    const [path, init] = apiFetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/api/v1/attendees/')
    expect(init.method).toBe('POST')
    // Story 5.3: тело — FormData (multipart), не JSON.
    const body = init.body as FormData
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('iin')).toBe('900515312349')
    expect(body.get('request')).toBe('1')
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled())
  })

  it('AC-4: серверная RFC7807-ошибка с field → под нужным полем', async () => {
    const { ApiError } = await import('@/api/client')
    apiFetchMock.mockRejectedValue(
      new ApiError(400, 'Ошибка', { title: 'Ошибка', detail: 'Дубликат ИИН', field: 'iin' }),
    )
    renderForm()
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория А/ })
    set(/Категория/, '1')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() =>
      expect(screen.getByText('Дубликат ИИН')).toBeInTheDocument(),
    )
  })

  it('Story 5.3: выбранное фото уходит в FormData', async () => {
    apiFetchMock.mockResolvedValue({ id: 1 })
    renderForm()
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория А/ })
    set(/Категория/, '1')
    const file = new File([new Uint8Array([1, 2, 3])], 'photo.jpg', { type: 'image/jpeg' })
    fireEvent.change(screen.getByLabelText(/ФОТО УЧАСТНИКА/), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1))
    const [, init] = apiFetchMock.mock.calls[0] as [string, RequestInit]
    const body = init.body as FormData
    const sent = body.get('photo')
    expect(sent).toBeInstanceOf(File)
    expect((sent as File).name).toBe('photo.jpg')
  })

  it('Story 5.3: серверная ошибка field:photo → под зоной фото', async () => {
    const { ApiError } = await import('@/api/client')
    apiFetchMock.mockRejectedValue(
      new ApiError(400, 'Ошибка', {
        title: 'Ошибка',
        detail: 'Файл слишком большой (максимум 5 МБ)',
        field: 'photo',
      }),
    )
    renderForm()
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория А/ })
    set(/Категория/, '1')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() =>
      expect(
        screen.getByText('Файл слишком большой (максимум 5 МБ)'),
      ).toBeInTheDocument(),
    )
  })
})

describe('AttendeeForm — черновик localStorage (Story 5.4)', () => {
  const KEY = 'attendee_draft_v1'

  beforeEach(() => {
    apiFetchMock.mockReset()
    toastSuccess.mockReset()
    toastError.mockReset()
    localStorage.clear()
  })

  it('AC-1: ввод → через 2с черновик в localStorage + индикатор', async () => {
    vi.useFakeTimers()
    try {
      renderForm()
      set('Фамилия', 'Черновиков')
      await act(async () => {
        vi.advanceTimersByTime(2000)
      })
      const raw = localStorage.getItem(KEY)
      expect(raw).toBeTruthy()
      expect(JSON.parse(raw as string).surname).toBe('Черновиков')
      expect(screen.getByText(/Черновик сохранён/)).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('AC-1: пустая форма не создаёт черновик', async () => {
    vi.useFakeTimers()
    try {
      renderForm()
      set('Фамилия', 'A')
      set('Фамилия', '') // вернули в пустое → не значимо
      await act(async () => {
        vi.advanceTimersByTime(2000)
      })
      expect(localStorage.getItem(KEY)).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('AC-2/3: предзаписанный черновик → баннер; «Да» восстанавливает поля', async () => {
    localStorage.setItem(KEY, JSON.stringify({ surname: 'Восстановленный', request: '7' }))
    renderForm()
    expect(screen.getByText(/Найден несохранённый черновик/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Да' }))
    await waitFor(() =>
      expect((screen.getByLabelText('Фамилия') as HTMLInputElement).value).toBe(
        'Восстановленный',
      ),
    )
    expect((screen.getByLabelText(/Категория/) as HTMLInputElement).value).toBe('7')
  })

  it('AC-3: «Начать заново» очищает черновик и форму', async () => {
    localStorage.setItem(KEY, JSON.stringify({ surname: 'Удаляемый' }))
    renderForm()
    fireEvent.click(screen.getByRole('button', { name: 'Начать заново' }))
    await waitFor(() =>
      expect(screen.queryByText(/Найден несохранённый/)).not.toBeInTheDocument(),
    )
    expect(localStorage.getItem(KEY)).toBeNull()
    expect((screen.getByLabelText('Фамилия') as HTMLInputElement).value).toBe('')
  })

  it('AC-4: успешный submit удаляет черновик', async () => {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        surname: 'Тестов',
        firstname: 'Тест',
        birthDate: '1990-05-15',
        countryId: '1000000105',
        iin: '900515312349',
        request: '1',
      }),
    )
    apiFetchMock.mockResolvedValue({ id: 1 })
    renderForm()
    fireEvent.click(screen.getByRole('button', { name: 'Да' }))
    await waitFor(() =>
      expect((screen.getByLabelText('Фамилия') as HTMLInputElement).value).toBe('Тестов'),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(localStorage.getItem(KEY)).toBeNull())
  })
})

describe('AttendeeForm — инвалидация кэша (Story 5.5)', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    toastSuccess.mockReset()
    toastError.mockReset()
    localStorage.clear()
  })

  it('AC-6: успешный submit → invalidateQueries(["attendees"])', async () => {
    apiFetchMock.mockResolvedValue({ id: 1 })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const spy = vi.spyOn(qc, 'invalidateQueries')
    render(
      <QueryClientProvider client={qc}>
        <AttendeeForm />
      </QueryClientProvider>,
    )
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория А/ })
    set(/Категория/, '1')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({ queryKey: ['attendees'] }),
    )
  })

  // ── P2-6: поле «request» (мероприятие) read-only в режиме редактирования ──
  // FE-1: поле теперь <select> → read-only выражается через `disabled`.
  it('P2-6: request disabled в edit (нельзя «переселить» участника)', () => {
    renderForm(
      <AttendeeForm
        attendeeId={5}
        initialValues={{ surname: 'И', request: '1', countryId: '643' }}
      />,
    )
    const field = screen.getByLabelText(/Категория/) as HTMLSelectElement
    expect(field.tagName).toBe('SELECT')
    expect(field.disabled).toBe(true)
  })

  it('P2-6: request редактируемо при добавлении', () => {
    renderForm()
    const field = screen.getByLabelText(/Категория/) as HTMLSelectElement
    expect(field.disabled).toBe(false)
  })

  // ── P2-7: edit показывает уже загруженные фото/документ ──────────────────
  it('P2-7: edit предзаполняет превью текущего фото и документа', () => {
    renderForm(
      <AttendeeForm
        attendeeId={5}
        initialValues={{ surname: 'И', request: '1', countryId: '643' }}
        initialPhotoUrl="/media/event_1/5_photo.jpg"
        initialDocScanUrl="/media/event_1/5_doc.jpg"
      />,
    )
    const photo = screen.getByAltText(/Текущее: ФОТО УЧАСТНИКА/i)
    expect(photo).toHaveAttribute('src', '/media/event_1/5_photo.jpg')
    const doc = screen.getByAltText(/Текущее: ФОТО ДОКУМЕНТА/i)
    expect(doc).toHaveAttribute('src', '/media/event_1/5_doc.jpg')
  })

  it('P2-7: при добавлении превью «текущего» нет', () => {
    renderForm()
    expect(screen.queryByAltText(/Текущее:/i)).not.toBeInTheDocument()
  })
})

describe('AttendeeForm — селектор категории (FE-1)', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    localStorage.clear()
  })

  it('add: поле «Категория» — <select> с RBAC-scoped опциями из getRequests', async () => {
    renderForm()
    const field = await screen.findByLabelText(/Категория/)
    expect(field.tagName).toBe('SELECT')
    expect(
      await screen.findByRole('option', { name: /Категория А/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Категория Б/ })).toBeInTheDocument()
  })

  it('add: выбор категории уходит в submit как request=id', async () => {
    apiFetchMock.mockResolvedValue({ id: 1 })
    renderForm()
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория Б/ })
    set(/Категория/, '2')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1))
    const [, init] = apiFetchMock.mock.calls[0] as [string, RequestInit]
    expect((init.body as FormData).get('request')).toBe('2')
  })
})
