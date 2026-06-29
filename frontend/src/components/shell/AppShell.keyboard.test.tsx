import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import i18n from '@/i18n'

const checkSessionMock = vi.fn()
vi.mock('@/api/auth', () => ({ checkSession: () => checkSessionMock() }))

import { AppShell } from './AppShell'
import { Button } from '@/components/ui/button'

function renderShell(role = 'operator') {
  checkSessionMock.mockResolvedValue({ role })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
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
}

describe('AppShell keyboard / a11y-примитивы (fe-2.5 AC-2/AC-3)', () => {
  beforeEach(() => checkSessionMock.mockReset())
  // тест меняет глобальную локаль + <html lang> → восстанавливаем ru явно (vitest.setup форсит ru)
  afterEach(async () => {
    await i18n.changeLanguage('ru')
    document.documentElement.lang = 'ru'
  })

  it('AC-2: skip-link — первый фокусируемый по Tab, ведёт в #main-content', async () => {
    const user = userEvent.setup()
    renderShell()
    await screen.findByText('Участники') // nav populated
    await user.tab()
    const active = document.activeElement
    expect(active?.tagName).toBe('A')
    expect(active).toHaveAttribute('href', '#main-content')
    expect(active).toHaveTextContent('Перейти к содержимому')
  })

  it('AC-2: <main> — фокусируемая цель скип-линка (id=main-content, tabIndex=-1)', async () => {
    renderShell()
    await screen.findByText('Участники')
    const main = screen.getByRole('main')
    expect(main).toHaveAttribute('id', 'main-content')
    expect(main).toHaveAttribute('tabindex', '-1')
    main.focus()
    expect(document.activeElement).toBe(main)
  })

  it('AC-3: <html lang> следует за локалью (kz → kk)', async () => {
    renderShell()
    await screen.findByText('Участники')
    await i18n.changeLanguage('kz')
    expect(document.documentElement.lang).toBe('kk')
  })

  it('AC-3: интерактивные элементы несут видимый фокус-ринг primary (button + nav + свитчер)', async () => {
    // Button-примитив
    const { getByRole, unmount } = render(<Button>кнопка</Button>)
    expect(getByRole('button')).toHaveClass('focus-visible:ring-primary')
    unmount()
    // nav-ссылки + кнопки LanguageSwitcher в каркасе (AC-3 «на ВСЕХ интерактивных»)
    renderShell()
    const navLink = (await screen.findByText('Участники')).closest('a')
    expect(navLink).toHaveClass('focus-visible:ring-primary')
    expect(screen.getByRole('button', { name: 'KZ' })).toHaveClass('focus-visible:ring-primary')
  })
})
