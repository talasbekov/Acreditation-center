import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { runAxe, criticalOrSerious } from '@/test/axe'
import type { Attendee, Paginated } from '@/types/attendee'

const getAttendeesMock = vi.fn()
vi.mock('@/api/attendees', () => ({
  getAttendees: (...a: unknown[]) => getAttendeesMock(...a),
}))

import { ReturnsInboxPage } from './ReturnsInboxPage'

function row(over: Partial<Attendee> = {}): Attendee {
  return {
    id: 7,
    surname: 'Беков',
    firstname: 'Асхат',
    patronymic: null,
    status: 'submitted',
    category: null,
    dateAdd: '2026-06-20T10:00:00Z',
    iin_masked: '********1234',
    last_return_reason: 'Нет фото',
    return_count: 3,
    ...over,
  }
}
function page(results: Attendee[]): Paginated<Attendee> {
  return { count: results.length, next: null, previous: null, results }
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/notifications']}>
        <Routes>
          <Route path="/notifications" element={<ReturnsInboxPage />} />
          <Route path="/attendees/:id" element={<div>EDIT-PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getAttendeesMock.mockReset()
})

describe('ReturnsInboxPage (fe-3.7)', () => {
  it('AC-1: запрос списка с returned=true', async () => {
    getAttendeesMock.mockResolvedValue(page([row()]))
    renderPage()
    await screen.findByText('Беков Асхат')
    expect(getAttendeesMock).toHaveBeenCalledWith(expect.objectContaining({ returned: true }))
  })

  it('AC-3: строка возврата — ФИО, маск-ИИН, причина, счётчик', async () => {
    getAttendeesMock.mockResolvedValue(page([row()]))
    renderPage()
    expect(await screen.findByText('Беков Асхат')).toBeInTheDocument()
    expect(screen.getByText('********1234')).toBeInTheDocument()
    expect(screen.getByText('Нет фото')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument() // return_count
  })

  it('AC-3: сырого 12-значного ИИН нет в DOM (masked-инвариант)', async () => {
    getAttendeesMock.mockResolvedValue(page([row()]))
    const { container } = renderPage()
    await screen.findByText('Беков Асхат')
    expect((container.textContent ?? '').match(/\d{12}/)).toBeNull()
  })

  it('AC-2/AC-3: пустое состояние «нет возвратов» — отдельный copy', async () => {
    getAttendeesMock.mockResolvedValue(page([]))
    renderPage()
    expect(
      await screen.findByText('Нет возвратов — всё отправлено на проверку.'),
    ).toBeInTheDocument()
  })

  it('AC-3: клик по строке → EditAttendeePage (/attendees/:id)', async () => {
    getAttendeesMock.mockResolvedValue(page([row()]))
    renderPage()
    fireEvent.click(await screen.findByText('Беков Асхат'))
    expect(await screen.findByText('EDIT-PAGE')).toBeInTheDocument()
  })

  it('AC-3: axe-0 (нет critical/serious)', async () => {
    getAttendeesMock.mockResolvedValue(page([row()]))
    const { container } = renderPage()
    await screen.findByText('Беков Асхат')
    const results = await runAxe(container)
    expect(criticalOrSerious(results)).toEqual([])
  })
})
