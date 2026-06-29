import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const checkSessionMock = vi.fn()
vi.mock('@/api/auth', () => ({ checkSession: () => checkSessionMock() }))

import { AppShell } from './AppShell'
import { runAxe, criticalOrSerious } from '@/test/axe'

describe('AppShell a11y (fe-2.5 AC-1)', () => {
  beforeEach(() => checkSessionMock.mockReset())

  it('ноль critical/serious нарушений axe на каркасе (под role)', async () => {
    checkSessionMock.mockResolvedValue({ role: 'superuser' })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<div>контент</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await screen.findByText('Очередь проверки') // дождаться populated nav (роль разрешилась)
    // скан по document.body (а не RTL-container) → корректный page-scope для каркаса-страницы
    const violations = criticalOrSerious(await runAxe(document.body))
    expect(violations.map((v) => v.id)).toEqual([])
  })
})
