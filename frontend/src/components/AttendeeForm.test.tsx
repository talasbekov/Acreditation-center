import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

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

import { AttendeeForm } from './AttendeeForm'

function set(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

describe('AttendeeForm (Story 5.2)', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    toastSuccess.mockReset()
    toastError.mockReset()
  })

  it('AC-3: страна ≠ Казахстан → поле ИИН исчезает', async () => {
    render(<AttendeeForm />)
    expect(screen.getByLabelText('ИИН')).toBeInTheDocument()
    set('Страна', '643')
    await waitFor(() =>
      expect(screen.queryByLabelText('ИИН')).not.toBeInTheDocument(),
    )
  })

  it('AC-2: резидент + неверная контрольная цифра → inline-ошибка', async () => {
    render(<AttendeeForm />)
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312340') // контрольная цифра неверна
    await waitFor(() =>
      expect(screen.getByText(/неверная контрольная цифра/i)).toBeInTheDocument(),
    )
  })

  it('AC-2: несовпадение даты рождения → сообщение с DD.MM.YYYY', async () => {
    render(<AttendeeForm />)
    set('Дата рождения', '1990-05-16')
    set('ИИН', '900515312349') // валидный ИИН на 15.05.1990
    await waitFor(() =>
      expect(screen.getByText(/не совпадает с введённой/i)).toBeInTheDocument(),
    )
  })

  it('AC-2 (патч): смена даты ПОСЛЕ валидного ИИН перевалидирует cross-field', async () => {
    render(<AttendeeForm />)
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
    render(<AttendeeForm />)
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    set(/Категория/, '1')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(apiFetchMock).toHaveBeenCalledTimes(1))
    const [path, init] = apiFetchMock.mock.calls[0] as [string, RequestInit]
    expect(path).toBe('/api/v1/attendees/')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    expect(body.iin).toBe('900515312349')
    expect(body.request).toBe(1)
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled())
  })

  it('AC-4: серверная RFC7807-ошибка с field → под нужным полем', async () => {
    const { ApiError } = await import('@/api/client')
    apiFetchMock.mockRejectedValue(
      new ApiError(400, 'Ошибка', { title: 'Ошибка', detail: 'Дубликат ИИН', field: 'iin' }),
    )
    render(<AttendeeForm />)
    set('Фамилия', 'Тестов')
    set('Имя', 'Тест')
    set('Дата рождения', '1990-05-15')
    set('ИИН', '900515312349')
    set(/Категория/, '1')
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() =>
      expect(screen.getByText('Дубликат ИИН')).toBeInTheDocument(),
    )
  })
})
