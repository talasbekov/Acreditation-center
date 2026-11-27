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

// Этап D: справочники формы (пол, типы документов, категории, страны).
vi.mock('@/api/directories', () => ({
  getDirectories: () =>
    Promise.resolve({
      sexes: [{ code: '1', name: 'Мужской' }],
      document_types: [{ code: '1000000002', name: 'Паспорт' }],
      categories: [{ code: '8', name: 'Гость' }],
      countries: [
        { code: '1000000105', name: 'Казахстан' },
        { code: '643', name: 'Россия' },
      ],
    }),
}))

import { AttendeeForm } from './AttendeeForm'

// FE-1: дефолтный список категорий для всех тестов (id=1 нужен существующим
// кейсам `set('Заявка', '1')`). Top-level beforeEach → раньше describe-scoped.
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

/** Этап D: остальные обязательные поля (как у HTML-формы). */
async function fillRest() {
  await screen.findByRole('option', { name: 'Мужской' })
  set('Имя латиницей', 'TESTOV TEST')
  set('Пол', '1')
  set('Должность', 'Инженер')
  set('Тип документа', '1000000002')
  set('Номер документа', 'N1')
  set('Дата выдачи', '2020-01-01')
  set('Действителен до', '2034-01-01')
  set('Объекты посещения', 'Зал')
}

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
    await screen.findByRole('option', { name: 'Россия' })
    set('Гражданство', '643')
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
    set('Заявка', '1')
    await fillRest()
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
    expect(screen.getByLabelText('Фамилия')).toHaveValue('')
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
    set('Заявка', '1')
    await fillRest()
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() =>
      expect(screen.getByText('Дубликат ИИН')).toBeInTheDocument(),
    )
    expect(screen.getByLabelText('Фамилия')).toHaveValue('Тестов')
  })

  it('Story 5.3: выбранное фото уходит в FormData', async () => {
    apiFetchMock.mockResolvedValue({ id: 1 })
    renderForm()
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория А/ })
    set('Заявка', '1')
    const file = new File([new Uint8Array([1, 2, 3])], 'photo.jpg', { type: 'image/jpeg' })
    fireEvent.change(screen.getByLabelText(/Фото участника/), { target: { files: [file] } })
    await fillRest()
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
    set('Заявка', '1')
    await fillRest()
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() =>
      expect(
        screen.getByText('Файл слишком большой (максимум 5 МБ)'),
      ).toBeInTheDocument(),
    )
  })
})

describe('AttendeeForm — общее рабочее место', () => {
  it('ввод остаётся только в открытой форме', async () => {
    vi.useFakeTimers()
    try {
      const { unmount } = renderForm()
      const writes = vi.spyOn(Storage.prototype, 'setItem')
      set('Фамилия', 'Черновиков')
      set('Дата рождения', '1990-05-15')
      set('ИИН', '900515312349')
      await act(async () => { vi.advanceTimersByTime(3000) })
      expect(writes).not.toHaveBeenCalled()
      expect(screen.getByLabelText('Фамилия')).toHaveValue('Черновиков')
      expect(screen.getByText(/До сохранения данные доступны только в открытой форме/)).toBeVisible()
      unmount()
      renderForm()
      expect(screen.getByLabelText('Фамилия')).toHaveValue('')
      expect(screen.getByLabelText('ИИН')).toHaveValue('')
    } finally {
      vi.restoreAllMocks()
      vi.useRealTimers()
    }
  })

  it('чужой старый черновик не предлагается и не блокирует ввод', () => {
    localStorage.setItem('attendee_draft_v1', JSON.stringify({ surname: 'Старый' }))
    renderForm()
    expect(screen.queryByText(/Восстановить/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Фамилия')).toBeEnabled()
    expect(screen.getByLabelText('Фамилия')).toHaveValue('')
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
    set('Заявка', '1')
    await fillRest()
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
    const field = screen.getByLabelText('Заявка') as HTMLSelectElement
    expect(field.tagName).toBe('SELECT')
    expect(field.disabled).toBe(true)
  })

  it('P2-6: request редактируемо при добавлении', () => {
    renderForm()
    const field = screen.getByLabelText('Заявка') as HTMLSelectElement
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
    const photo = screen.getByAltText(/Текущее: Фото участника/i)
    expect(photo).toHaveAttribute('src', '/media/event_1/5_photo.jpg')
    const doc = screen.getByAltText(/Текущее: Скан документа/i)
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
    const field = await screen.findByLabelText('Заявка')
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
    set('Заявка', '2')
    await fillRest()
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1))
    const [, init] = apiFetchMock.mock.calls[0] as [string, RequestInit]
    expect((init.body as FormData).get('request')).toBe('2')
  })
})

describe('AttendeeForm — эталон этапа D', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    toastError.mockReset()
  })

  it('пустая форма: сводка ошибок со ссылками, фокус на первом поле с ошибкой, запроса нет', async () => {
    renderForm()
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    const summary = await screen.findByRole('alert', { name: /Не сохранено: исправьте поля/ })
    await waitFor(() => expect(screen.getByLabelText('Фамилия')).toHaveFocus())
    const links = Array.from(summary.querySelectorAll('a')).map((a) => a.getAttribute('href'))
    expect(links).toEqual([
      '#surname', '#firstname', '#transcription', '#birthDate', '#sexId', '#post', '#iin',
      '#docTypeId', '#docNumber', '#docBegin', '#docEnd', '#request', '#visitObjects',
    ])
    expect(summary).toHaveTextContent('Фамилия: Укажите фамилию')
    expect(summary).toHaveTextContent('Заявка: Выберите заявку')
    fireEvent.click(screen.getByRole('link', { name: 'Имя: Укажите имя' }))
    expect(screen.getByLabelText('Имя')).toHaveFocus()
    expect(apiFetchMock).not.toHaveBeenCalled()
  })

  it('поля связаны с ошибкой и подсказкой, обязательность объявлена', async () => {
    renderForm()
    const surname = screen.getByLabelText('Фамилия')
    expect(surname).toHaveAttribute('aria-required', 'true')
    expect(screen.getByLabelText('Отчество')).not.toHaveAttribute('aria-required')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(surname).toHaveAttribute('aria-invalid', 'true'))
    expect(surname).toHaveAccessibleDescription('Укажите фамилию')
    expect(screen.getByLabelText('ИИН')).toHaveAccessibleDescription(/12 цифр/)
  })

  it('ошибка сервера по полю попадает и в сводку', async () => {
    const { ApiError } = await import('@/api/client')
    apiFetchMock.mockRejectedValue(new ApiError(400, 'Ошибка', { title: 'Ошибка', detail: 'Дубликат ИИН', field: 'iin' }))
    renderForm()
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория А/ })
    set('Заявка', '1')
    await fillRest()
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    const summary = await screen.findByRole('alert', { name: /Не сохранено: исправьте поле/ })
    expect(summary).toHaveTextContent('ИИН: Дубликат ИИН')
  })

  it('формат ИИН — текстом, кнопка «Отмена» из страницы', async () => {
    renderForm(<AttendeeForm cancel={<a href="/">Отмена</a>} />)
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    expect(await screen.findByText('✓ Формат ИИН верный')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Отмена' })).toBeInTheDocument()
  })

  it('все поля HTML-формы уходят на сервер; резиденту категория не отправляется', async () => {
    apiFetchMock.mockResolvedValue({ id: 1 })
    renderForm()
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория А/ })
    set('Заявка', '1')
    await fillRest()
    set('Серия', 'AB')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1))
    const body = (apiFetchMock.mock.calls[0] as [string, RequestInit])[1].body as FormData
    expect(Object.fromEntries(body.entries())).toMatchObject({
      transcription: 'TESTOV TEST', sexId: '1', post: 'Инженер', countryId: '1000000105', iin: '900515312349',
      stickId: '', docTypeId: '1000000002', docSeries: 'AB', docNumber: 'N1', docBegin: '2020-01-01',
      docEnd: '2034-01-01', docIssue: '', request: '1', visitObjects: 'Зал',
    })
  })

  it('нерезидент: ИИН скрыт, категория обязательна и уходит на сервер', async () => {
    apiFetchMock.mockResolvedValue({ id: 1 })
    renderForm()
    await screen.findByRole('option', { name: 'Россия' })
    set('Гражданство', '643')
    expect(screen.queryByLabelText('ИИН')).not.toBeInTheDocument()
    set('Фамилия', 'Смит')
    set('Имя', 'Джон')
    set('Дата рождения', '1990-05-15')
    await screen.findByRole('option', { name: /Категория А/ })
    set('Заявка', '1')
    await fillRest()
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByRole('link', { name: 'Категория: Выберите категорию' })).toBeInTheDocument()
    expect(apiFetchMock).not.toHaveBeenCalled()
    set('Категория', '8')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1))
    const body = (apiFetchMock.mock.calls[0] as [string, RequestInit])[1].body as FormData
    expect(body.get('stickId')).toBe('8')
    expect(body.get('iin')).toBe('')
  })

  it('даты при добавлении: документ уже выдан и ещё действует', async () => {
    renderForm()
    await fillRest()
    set('Дата выдачи', '2999-01-01')
    set('Действителен до', '2000-01-01')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByRole('link', { name: 'Дата выдачи: Дата выдачи документа еще не наступила' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Действителен до: Истек срок документа' })).toBeInTheDocument()
  })

  it('ошибки сервера по нескольким полям раскладываются по полям', async () => {
    const { ApiError } = await import('@/api/client')
    apiFetchMock.mockRejectedValue(
      new ApiError(400, 'Bad Request', {
        title: 'Bad Request',
        detail: 'post: Обязательное поле.; docNumber: Участник с этим документом уже добавлен в это мероприятие.',
        field: 'post',
        errors: { post: 'Обязательное поле.', docNumber: 'Участник с этим документом уже добавлен в это мероприятие.' },
      }),
    )
    renderForm()
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    await screen.findByRole('option', { name: /Категория А/ })
    set('Заявка', '1')
    await fillRest()
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    const summary = await screen.findByRole('alert', { name: /Не сохранено: исправьте поля/ })
    expect(summary).toHaveTextContent('Должность: Обязательное поле.')
    expect(summary).toHaveTextContent('Номер документа: Участник с этим документом уже добавлен в это мероприятие.')
    expect(screen.getByLabelText('Номер документа')).toHaveAttribute('aria-invalid', 'true')
  })

  it('правка: сохранённые коды справочников выбраны после загрузки списков', async () => {
    renderForm(
      <AttendeeForm
        attendeeId={5}
        initialValues={{ surname: 'И', request: '1', countryId: '643', sexId: '1', docTypeId: '1000000002', stickId: '8' }}
      />,
    )
    expect(await screen.findByDisplayValue('Россия')).toBeInTheDocument()
    expect(screen.getByLabelText('Пол')).toHaveValue('1')
    expect(screen.getByLabelText('Тип документа')).toHaveValue('1000000002')
    expect(screen.getByLabelText('Категория')).toHaveValue('8')
  })
})

