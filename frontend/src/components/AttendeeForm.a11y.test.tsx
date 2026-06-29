import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
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
import { runAxe, criticalOrSerious } from '@/test/axe'

beforeEach(() => {
  getRequestsMock.mockReset()
  getRequestsMock.mockResolvedValue([
    { id: 1, name: 'Категория А', event_id: 1, event_name: 'Событие 1' },
  ])
})

describe('AttendeeForm a11y (fe-2.5 AC-1, выборочно)', () => {
  it('ноль critical/serious нарушений axe', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { container } = render(
      <QueryClientProvider client={qc}>
        <AttendeeForm />
      </QueryClientProvider>,
    )
    // дождаться загрузки опций категории (option text = `{name} — {event_name}`) → форма стабильна.
    await screen.findByText(/Категория А/)
    const violations = criticalOrSerious(await runAxe(container))
    expect(violations.map((v) => v.id)).toEqual([])
  })
})
