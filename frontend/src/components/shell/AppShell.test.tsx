import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

// fe-2.2 AC-2: роль приходит от сервера через checkSession (rbac-check). Мокаем по роли.
// queryKey ['session-check'] — тот же, что в RequireAuth (reuse кэша, без второго запроса).
const checkSessionMock = vi.fn()
vi.mock('@/api/auth', () => ({
  checkSession: () => checkSessionMock(),
}))

// P2: интеграционный тест рендерит реальную AttendeesPage под AppShell → мок данных списка.
const getAttendeesMock = vi.fn()
vi.mock('@/api/attendees', () => ({
  getAttendees: () => getAttendeesMock(),
}))

import { AppShell } from './AppShell'
import { AttendeesPage } from '@/pages/AttendeesPage'
import { useRole } from '@/hooks/useRole'

// Второй consumer useRole — для проверки общего кэша ['session-check'] (P5).
function RoleProbe() {
  const role = useRole()
  return <span data-testid="probe-role">{role ?? 'pending'}</span>
}

// i18n инициализируется в vitest.setup.ts (форс ru) → t() работает без I18nextProvider.
function renderShell(role: string, initialEntries: string[] = ['/']) {
  checkSessionMock.mockResolvedValue({ role })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<div>главная-stub</div>} />
            <Route path="add" element={<div>добавить-stub</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AppShell (fe-2.2)', () => {
  beforeEach(() => {
    checkSessionMock.mockReset()
    getAttendeesMock.mockReset()
  })

  it('AC-1: рендерит лендмарки header/nav/main; main имеет id="main-content"', async () => {
    renderShell('operator')
    await screen.findByText('Участники') // дождаться popul. nav (роль разрешилась)
    expect(screen.getByRole('navigation')).toBeInTheDocument()
    const main = screen.getByRole('main')
    expect(main).toBeInTheDocument()
    expect(main).toHaveAttribute('id', 'main-content')
    // контент роута рендерится внутри <main> (Outlet)
    expect(main).toHaveTextContent('главная-stub')
  })

  it('AC-2: operator видит свои пункты, но НЕ admin-only (Журнал/Экспорт отсутствуют в DOM)', async () => {
    renderShell('operator')
    await screen.findByText('Участники')
    expect(screen.getByText('Добавить участника')).toBeInTheDocument()
    expect(screen.getByText('Уведомления')).toBeInTheDocument()
    expect(screen.queryByText('Журнал')).not.toBeInTheDocument()
    expect(screen.queryByText('Экспорт')).not.toBeInTheDocument()
    expect(screen.queryByText('Очередь проверки')).not.toBeInTheDocument()
  })

  it('AC-2: superuser видит admin-only пункты (Очередь/Журнал/Экспорт)', async () => {
    renderShell('superuser')
    await screen.findByText('Очередь проверки')
    expect(screen.getByText('Журнал')).toBeInTheDocument()
    expect(screen.getByText('Экспорт')).toBeInTheDocument()
  })

  it('AC-3: активный пункт несёт aria-current="page", неактивный — нет', async () => {
    renderShell('operator', ['/'])
    const active = await screen.findByText('Участники')
    expect(active.closest('a')).toHaveAttribute('aria-current', 'page')
    const inactive = screen.getByText('Уведомления')
    expect(inactive.closest('a')).not.toHaveAttribute('aria-current')
  })

  it('AC-4: skip-link — первая ссылка в DOM, ведёт в #main-content, скрыт до фокуса', async () => {
    const { container } = renderShell('operator')
    await screen.findByText('Участники')
    const firstLink = container.querySelector('a')
    expect(firstLink).toHaveAttribute('href', '#main-content')
    expect(firstLink).toHaveTextContent('Перейти к содержимому')
    // скрыт до фокуса: sr-only, раскрывается на focus:not-sr-only
    expect(firstLink?.className).toContain('sr-only')
    expect(firstLink?.className).toContain('focus:not-sr-only')
  })

  it('AC-2: useRole делит кэш ["session-check"] — два consumer’а → ровно один fetch', async () => {
    checkSessionMock.mockResolvedValue({ role: 'superoperator' })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/']}>
          <RoleProbe />
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<div>stub</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    // оба consumer’а (RoleProbe + useRole внутри AppShell) видят роль…
    await screen.findByText('События')
    expect(screen.getByTestId('probe-role')).toHaveTextContent('superoperator')
    // …но staleTime:Infinity + общий ключ → ровно один сетевой вызов на двоих (без refetchOnMount)
    expect(checkSessionMock).toHaveBeenCalledTimes(1)
  })

  it('AC-1/AC-5 (регрессия): реальная страница под AppShell → ровно один <main> landmark', async () => {
    checkSessionMock.mockResolvedValue({ role: 'operator' })
    getAttendeesMock.mockResolvedValue({ count: 0, results: [] })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<AttendeesPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await screen.findByText('Добавить участника') // nav популяция (роль резолвилась)
    // shell даёт единственный <main>; страницы демоутнуты на <div> (анти-вложенный-main)
    expect(screen.getAllByRole('main')).toHaveLength(1)
  })
})
