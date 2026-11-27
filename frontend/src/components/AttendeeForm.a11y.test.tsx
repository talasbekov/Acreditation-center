import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Мок-паттерн из AttendeeForm.test.tsx (apiFetch/sonner/getRequests/getDirectories).
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
const getRequestsMock = vi.fn()
vi.mock('@/api/requests', () => ({ getRequests: () => getRequestsMock() }))
vi.mock('@/api/directories', () => ({
  getDirectories: () =>
    Promise.resolve({
      sexes: [{ code: '1', name: 'Мужской' }],
      countries: [{ code: '1000000105', name: 'Казахстан' }],
      document_types: [{ code: '1', name: 'Паспорт' }],
      categories: [{ code: '1', name: 'Пресса' }],
    }),
}))

import { AttendeeForm } from './AttendeeForm'
import { PhotoUpload } from '@/components/PhotoUpload/PhotoUpload'
import { runAxe, criticalOrSerious } from '@/test/axe'

beforeEach(() => {
  getRequestsMock.mockReset()
  getRequestsMock.mockResolvedValue([
    { id: 1, name: 'Категория А', event_id: 1, event_name: 'Событие 1' },
  ])
})

function renderForm(ui = <AttendeeForm />) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

const el = (sel: string) => document.querySelector(sel) as HTMLInputElement

// Форма этапа D (все поля HTML-формы). По умолчанию гражданство — Казахстан, поэтому
// вместо категории показан ИИН.
const REQUIRED = [
  'surname',
  'firstname',
  'transcription',
  'birthDate',
  'sexId',
  'post',
  'countryId',
  'iin',
  'docTypeId',
  'docNumber',
  'docBegin',
  'docEnd',
  'request',
  'visitObjects',
]
const OPTIONAL = ['patronymic', 'docSeries', 'docIssue', 'photo', 'docScan']

describe('AttendeeForm a11y (fe-2.5 AC-1, выборочно)', () => {
  it('ноль critical/serious нарушений axe', async () => {
    const { container } = renderForm()
    // дождаться загрузки опций категории (option text = `{name} — {event_name}`) → форма стабильна.
    await screen.findByText(/Категория А/)
    const violations = criticalOrSerious(await runAxe(container))
    expect(violations.map((v) => v.id)).toEqual([])
  })
})

describe('AttendeeForm a11y (fe-2.7 AC-1: обязательность + связка ошибки)', () => {
  it('обязательное поле — aria-required и видимая звёздочка у метки; необязательное — без них', async () => {
    renderForm()
    await screen.findByText(/Категория А/)
    for (const id of REQUIRED) {
      expect(el(`#${id}`), id).toHaveAttribute('aria-required', 'true')
      const label = document.querySelector(`label[for="${id}"]`)!
      // Звёздочка — рядом с меткой (не внутри: имя поля для диктора остаётся точным).
      expect(label.parentElement?.textContent, id).toContain('*')
    }
    for (const id of OPTIONAL) {
      expect(el(`#${id}`), id).not.toHaveAttribute('aria-required')
    }
    // Значение звёздочки объяснено текстом над формой.
    expect(screen.getByText(/Поля со звёздочкой \* обязательны/)).toBeInTheDocument()
  })

  it('ошибка поля → aria-invalid + aria-describedby на узел с локализованным текстом', async () => {
    const user = userEvent.setup()
    renderForm()
    await screen.findByText(/Категория А/)
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    const surname = el('#surname')
    await waitFor(() => expect(document.getElementById('surname-error')).toHaveTextContent('Укажите фамилию'))
    expect(surname).toHaveAttribute('aria-invalid', 'true')
    expect(surname).toHaveAttribute('aria-describedby', 'surname-error')
    const errNode = document.getElementById('surname-error')!
    expect(errNode.textContent).not.toMatch(/validation:/) // локализовано, не ключ
  })
})

describe('AttendeeForm a11y (fe-2.7 AC-2: ИИН — один анонс после паузы)', () => {
  // Реальные таймеры + waitFor (пауза 500 мс): fake-timers зависают на user.type под
  // RHF/react-query. Быстрый ввод 12 цифр заканчивается до паузы → живой регион
  // меняется один раз.
  it('быстрый ввод 12 цифр → живой регион меняется РОВНО 1 раз (не 12), текст локализован', async () => {
    const user = userEvent.setup()
    renderForm()
    const iin = el('#iin')
    const live = screen.getByTestId('iin-live')
    let calls = 0
    const obs = new MutationObserver(() => {
      calls += 1
    })
    obs.observe(live, { childList: true, characterData: true, subtree: true })
    // Неверная контрольная цифра → детерминированный невалидный исход (без зависимости от даты).
    await user.type(iin, '900515312340')
    await waitFor(() => expect(live.textContent).toMatch(/контрольная цифра/))
    await new Promise((r) => setTimeout(r, 0)) // дать observer-колбэку (microtask) выполниться
    obs.disconnect()
    expect(calls).toBe(1)
    expect(live.textContent).not.toMatch(/validation:/)
    expect(iin.getAttribute('aria-describedby')).toContain('iin-live')
  })

  it('верный ИИН → живой регион сообщает, что формат верный', async () => {
    const user = userEvent.setup()
    renderForm()
    fireEvent.change(el('#birthDate'), { target: { value: '1990-05-15' } })
    const live = screen.getByTestId('iin-live')
    await user.type(el('#iin'), '900515312349') // верен для 15.05.1990
    await waitFor(() => expect(live.textContent).toMatch(/Формат ИИН верный/))
  })

  it('очистка ИИН → живой регион очищается (нет висящей ошибки)', async () => {
    const user = userEvent.setup()
    renderForm()
    const iin = el('#iin')
    const live = screen.getByTestId('iin-live')
    await user.type(iin, '900515312340')
    await waitFor(() => expect(live.textContent).not.toBe(''))
    await user.clear(iin)
    await waitFor(() => expect(live.textContent).toBe(''))
  })
})

describe('AttendeeForm a11y (fe-2.7 AC-3: зоны загрузки)', () => {
  it('поле зоны достижимо с клавиатуры и имеет доступное имя', async () => {
    renderForm()
    await screen.findByText(/Категория А/)
    const photo = el('#photo')
    expect(photo.type).toBe('file')
    // Имя через <label htmlFor> (Tab достижим, Enter/Space открывает диалог — 2.1.1).
    expect(screen.getByLabelText(/Фото участника/)).toBe(photo)
    expect(photo).not.toHaveAttribute('aria-invalid') // ошибки нет
  })

  it('причина отказа связана с зоной: aria-describedby + aria-invalid + role=alert', () => {
    render(<PhotoUpload file={null} onFileChange={() => {}} error="Файл слишком большой" />)
    const input = el('#photo')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input.getAttribute('aria-describedby')?.split(' ')).toContain('photo-error')
    const err = document.getElementById('photo-error')!
    expect(err).toHaveAttribute('role', 'alert')
    expect(err).toHaveTextContent('Файл слишком большой')
  })
})

describe('AttendeeForm a11y (fe-2.7 AC-4: axe с ошибками + проход клавиатурой)', () => {
  it('0 critical/serious axe в состоянии с ошибками', async () => {
    const user = userEvent.setup()
    const { container } = renderForm()
    await screen.findByText(/Категория А/)
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(document.getElementById('surname-error')).toBeInTheDocument())
    const violations = criticalOrSerious(await runAxe(container))
    expect(violations.map((v) => v.id)).toEqual([])
  })

  it('порядок Tab = порядок чтения', async () => {
    const user = userEvent.setup()
    renderForm()
    await screen.findByText(/Категория А/)
    const order = [
      'surname',
      'firstname',
      'patronymic',
      'transcription',
      'birthDate',
      'sexId',
      'post',
      'countryId',
      'iin',
      'docTypeId',
      'docSeries',
      'docNumber',
      'docIssue',
      'docBegin',
      'docEnd',
      'request',
      'visitObjects',
      'photo',
      'docScan',
    ]
    for (const id of order) {
      await user.tab()
      expect(document.activeElement?.id).toBe(id)
    }
    await user.tab()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Сохранить' }))
  })
})
