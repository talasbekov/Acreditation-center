import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Мок-паттерн из AttendeeForm.test.tsx (apiFetch/sonner/getRequests).
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
const getRequestsMock = vi.fn()
vi.mock('@/api/requests', () => ({ getRequests: () => getRequestsMock() }))

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
  it('обязательное поле — aria-required + видимое «(обязательно)»; patronymic — нет', async () => {
    renderForm()
    await screen.findByText(/Категория А/)
    // 6 обязательных полей (surname/firstname/birthDate/country/iin-резидент/request) → 6 маркеров.
    expect(screen.getAllByText('(обязательно)')).toHaveLength(6)
    for (const id of ['#surname', '#firstname', '#birthDate', '#countryId', '#iin', '#request']) {
      expect(el(id)).toHaveAttribute('aria-required', 'true')
    }
    // patronymic + upload-зоны (опциональны) — без aria-required.
    for (const id of ['#patronymic', '#photo', '#docScan']) {
      expect(el(id)).not.toHaveAttribute('aria-required')
    }
  })

  it('ошибка поля → aria-invalid + aria-describedby на узел с локализованным текстом', async () => {
    const user = userEvent.setup()
    renderForm()
    await screen.findByText(/Категория А/)
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    const surname = el('#surname')
    await screen.findByText('Укажите фамилию')
    expect(surname).toHaveAttribute('aria-invalid', 'true')
    expect(surname).toHaveAttribute('aria-describedby', 'surname-error')
    const errNode = document.getElementById('surname-error')!
    expect(errNode).toHaveTextContent('Укажите фамилию') // локализовано, не ключ validation:*
    expect(errNode.textContent).not.toMatch(/validation:/)
  })
})

describe('AttendeeForm a11y (fe-2.7 AC-2: real-time ИИН — анонс ровно 1 раз)', () => {
  // Реальные таймеры + waitFor (debounce 500мс реальный): fake-timers зависают на
  // user.type под RHF/react-query. Быстрый ввод 12 цифр заканчивается до debounce →
  // промежуточные target'ы не коммитятся, live-регион мутирует один раз на settle.
  it('быстрый ввод 12 цифр → live-регион мутирует РОВНО 1 раз (не 12), текст локализован', async () => {
    const user = userEvent.setup()
    renderForm()
    const iin = el('#iin')
    const live = screen.getByTestId('iin-live')
    let calls = 0
    const obs = new MutationObserver(() => {
      calls += 1
    })
    obs.observe(live, { childList: true, characterData: true, subtree: true })
    // Неверная контрольная цифра → детерминированный невалидный исход (без зависимости от dob).
    await user.type(iin, '900515312340')
    await waitFor(() => expect(live.textContent).toMatch(/контрольная цифра/))
    await new Promise((r) => setTimeout(r, 0)) // дать observer-колбэку (microtask) выполниться
    obs.disconnect()
    expect(calls).toBe(1) // ровно один settle-анонс (не 12 на каждую цифру)
    expect(live.textContent).not.toMatch(/validation:/) // локализовано, не ключ
    expect(live.textContent).not.toBe('')
  })

  it('валидный ИИН → live-регион содержит «корректен»', async () => {
    const user = userEvent.setup()
    renderForm()
    fireEvent.change(el('#birthDate'), { target: { value: '1990-05-15' } })
    const live = screen.getByTestId('iin-live')
    await user.type(el('#iin'), '900515312349') // валиден на 15.05.1990
    await waitFor(() => expect(live.textContent).toMatch(/корректен/))
  })

  it('очистка ИИН → live-регион очищается (нет висящей ошибки)', async () => {
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

describe('AttendeeForm a11y (fe-2.7 AC-3: upload-зоны)', () => {
  it('input зоны достижим с клавиатуры + имеет accessible name', async () => {
    renderForm()
    await screen.findByText(/Категория А/)
    const photo = el('#photo')
    expect(photo.type).toBe('file')
    // accessible name через <label htmlFor> (Tab достижим, Enter/Space открывает диалог — 2.1.1).
    expect(screen.getByLabelText(/ФОТО УЧАСТНИКА/)).toBe(photo)
    expect(photo).not.toHaveAttribute('aria-invalid') // ошибки нет → без describedby
  })

  it('причина отказа связана с зоной: aria-describedby + aria-invalid + role=alert', () => {
    render(
      <PhotoUpload file={null} onFileChange={() => {}} error="Файл слишком большой" />,
    )
    const input = el('#photo')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAttribute('aria-describedby', 'photo-error')
    const err = document.getElementById('photo-error')!
    expect(err).toHaveAttribute('role', 'alert')
    expect(err).toHaveTextContent('Файл слишком большой')
  })
})

describe('AttendeeForm a11y (fe-2.7 AC-4: axe error-state + keyboard-pass)', () => {
  it('0 critical/serious axe в error-состоянии (закрывает defer fe-2.5)', async () => {
    const user = userEvent.setup()
    const { container } = renderForm()
    await screen.findByText(/Категория А/)
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    await screen.findByText('Укажите фамилию') // ошибки отрисованы
    const violations = criticalOrSerious(await runAxe(container))
    expect(violations.map((v) => v.id)).toEqual([])
  })

  it('keyboard-pass — Tab-порядок = порядок чтения', async () => {
    const user = userEvent.setup()
    renderForm()
    await screen.findByText(/Категория А/)
    const order = [
      '#surname',
      '#firstname',
      '#patronymic',
      '#birthDate',
      '#countryId',
      '#iin',
      '#request',
      '#photo',
      '#docScan',
    ]
    for (const sel of order) {
      await user.tab()
      expect(document.activeElement).toBe(el(sel))
    }
    await user.tab()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Сохранить' }))
  })
})
