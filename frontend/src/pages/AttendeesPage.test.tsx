import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { registryState } from '@/lib/registryState'

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

function LocationProbe() {
  const loc = useLocation()
  return <output data-testid="location">{loc.pathname + loc.search}</output>
}

function renderPage(url = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <AttendeesPage />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function setViewport(desktop: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: desktop,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
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
  returned?: boolean
  request_name?: string
  event_name?: string
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
  registryState.reset()
  setViewport(true)
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

  it('этап C: подписи статусов как на HTML, возвращённый черновик отмечен', async () => {
    getAttendeesMock.mockResolvedValue(
      page(
        [
          { ...ROW, id: 1, surname: 'Первый', returned: true },
          { ...ROW, id: 2, surname: 'Второй', status: 'ready' },
          { ...ROW, id: 3, surname: 'Третий', status: 'submitted' },
        ],
        3,
      ),
    )
    renderPage()
    await waitFor(() =>
      expect(screen.getByText('Возвращён на доработку')).toBeInTheDocument(),
    )
    expect(screen.getAllByText('Допущен').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Отправлен на проверку').length).toBeGreaterThan(0)
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

  it('AC-5: имя — ссылка на карточку, щелчок по строке тоже открывает её', async () => {
    getAttendeesMock.mockResolvedValue(page([ROW], 1))
    renderPage()
    const link = await screen.findByRole('link', { name: 'Иванов Иван Иванович' })
    expect(link).toHaveAttribute('href', '/attendees/1')
    fireEvent.click(screen.getByText('01.06.2026'))
    expect(navigateMock).toHaveBeenCalledWith('/attendees/1')
    expect(registryState.get().lastOpenedId).toBe(1)
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

describe('AttendeesPage — эталон этапа D', () => {
  it('строка показывает заявку и мероприятие', async () => {
    getAttendeesMock.mockResolvedValue(page([{ ...ROW, request_name: 'A-01', event_name: 'Форум' }], 1))
    renderPage()
    expect(await screen.findByText('Заявка A-01')).toBeInTheDocument()
    expect(screen.getByText('Форум')).toBeInTheDocument()
  })

  it('статус и страница берутся из адреса и пишутся в него', async () => {
    getAttendeesMock.mockResolvedValue(page([ROW], 120, { next: 'x', previous: 'y' }))
    renderPage('/?status=ready&page=2')
    await waitFor(() =>
      expect(getAttendeesMock).toHaveBeenCalledWith(expect.objectContaining({ status: 'ready', page: 2 })),
    )
    expect(screen.getByLabelText('Фильтр по статусу')).toHaveValue('ready')
    fireEvent.change(screen.getByLabelText('Фильтр по статусу'), { target: { value: 'submitted' } })
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/?status=submitted'))
    expect(registryState.get().listUrl).toBe('/?status=submitted')
  })

  it('поиск (ФИО) не попадает в адрес, но восстанавливается при возврате', async () => {
    getAttendeesMock.mockResolvedValue(page([ROW], 1))
    const first = renderPage()
    fireEvent.change(screen.getByLabelText('Поиск по ФИО'), { target: { value: 'Иванов' } })
    await waitFor(() =>
      expect(getAttendeesMock).toHaveBeenCalledWith(expect.objectContaining({ search: 'Иванов' })),
    )
    expect(screen.getByTestId('location').textContent).not.toContain('Иванов')
    first.unmount()
    getAttendeesMock.mockClear()
    renderPage()
    expect(screen.getByLabelText('Поиск по ФИО')).toHaveValue('Иванов')
    await waitFor(() =>
      expect(getAttendeesMock).toHaveBeenCalledWith(expect.objectContaining({ search: 'Иванов' })),
    )
  })

  it('короткий запрос — подсказка', async () => {
    getAttendeesMock.mockResolvedValue(page([ROW], 1))
    renderPage()
    fireEvent.change(screen.getByLabelText('Поиск по ФИО'), { target: { value: 'Ив' } })
    expect(screen.getByText(/Введите ещё 1 — поиск начинается с 3 символов/)).toBeInTheDocument()
  })

  it('пустая база и пустая выборка различаются', async () => {
    getAttendeesMock.mockResolvedValue(page([], 0))
    const view = renderPage()
    expect(await screen.findByText('Участников пока нет')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Добавить первого участника' })).toBeInTheDocument()
    view.unmount()
    renderPage('/?status=ready')
    expect(await screen.findByText('Ничего не найдено')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Сбросить фильтры' })[0])
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/'))
  })

  it('ошибка загрузки — сообщение и «Повторить»', async () => {
    getAttendeesMock.mockRejectedValueOnce(new Error('down')).mockResolvedValue(page([ROW], 1))
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Не удалось загрузить список.')
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await screen.findByText('Иванов Иван Иванович')).toBeInTheDocument()
  })

  it('узкий экран: карточки-ссылки и раскрываемые фильтры', async () => {
    setViewport(false)
    getAttendeesMock.mockResolvedValue(page([{ ...ROW, request_name: 'A-01', event_name: 'Форум' }], 1))
    renderPage('/?status=draft')
    const card = await screen.findByRole('link', { name: /Иванов Иван Иванович/ })
    expect(card).toHaveAttribute('href', '/attendees/1')
    expect(card).toHaveTextContent('Заявка A-01 · Форум')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    const toggle = screen.getByRole('button', { name: 'Фильтры · 1' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByLabelText('Фильтр по статусу')).not.toBeInTheDocument()
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByLabelText('Фильтр по статусу')).toHaveValue('draft')
  })

  it('возврат из карточки — фокус на строке открытого участника', async () => {
    registryState.set({ lastOpenedId: 2 })
    getAttendeesMock.mockResolvedValue(page([ROW, { ...ROW, id: 2, surname: 'Петров' }], 2))
    renderPage()
    const link = await screen.findByRole('link', { name: 'Петров Иван Иванович' })
    await waitFor(() => expect(link).toHaveFocus())
    expect(registryState.get().lastOpenedId).toBeNull()
  })
})
