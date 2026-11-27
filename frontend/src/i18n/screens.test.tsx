import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import i18n from '@/i18n'

// Экраны этапа D переведены на ключи (ru/kz/en): переключение языка меняет и форму,
// и реестр, и сообщения проверки.
vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock('@/api/requests', () => ({ getRequests: () => Promise.resolve([]) }))
vi.mock('@/api/directories', () => ({
  getDirectories: () => Promise.resolve({ sexes: [], countries: [], document_types: [], categories: [] }),
}))
vi.mock('@/api/attendees', () => ({
  getAttendees: () =>
    Promise.resolve({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 7,
          surname: 'Иванов',
          firstname: 'Иван',
          patronymic: '',
          status: 'ready',
          category: null,
          dateAdd: '2026-11-27T10:00:00Z',
          iin_masked: '********1234',
          returned: false,
          request_name: '01',
          event_name: 'Форум',
          return_count: 0,
        },
      ],
    }),
}))

import { AttendeeForm } from '@/components/AttendeeForm'
import { AttendeesPage } from '@/pages/AttendeesPage'

function renderWithProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(async () => {
  await i18n.changeLanguage('ru')
})

describe('экраны оператора на трёх языках', () => {
  it.each([
    ['kz', 'Тегі', 'ЖСН', 'Сақтау'],
    ['en', 'Surname', 'IIN', 'Save'],
  ])('форма участника: %s', async (lang, surname, iin, save) => {
    await i18n.changeLanguage(lang)
    renderWithProviders(<AttendeeForm />)
    expect(screen.getByLabelText(surname)).toBeInTheDocument()
    expect(screen.getByLabelText(iin)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: save })).toBeInTheDocument()
  })

  it.each([
    ['kz', 'Қатысушылар', 'Рұқсат етілді'],
    ['en', 'Attendees', 'Approved'],
  ])('реестр: %s', async (lang, title, status) => {
    await i18n.changeLanguage(lang)
    renderWithProviders(<AttendeesPage />)
    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByText(status).length).toBeGreaterThan(0))
  })
})
