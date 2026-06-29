import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider, useTheme, THEME_STORAGE_KEY } from './ThemeProvider'

// Тема пишет в глобальные documentElement.classList + localStorage → чистим между тестами.
afterEach(() => {
  document.documentElement.classList.remove('dark')
  localStorage.clear()
})

function ThemeProbe() {
  const { theme, setTheme } = useTheme()
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <button type="button" onClick={() => setTheme('dark')}>
        go-dark
      </button>
      <button type="button" onClick={() => setTheme('light')}>
        go-light
      </button>
    </div>
  )
}

describe('ThemeProvider (fe-2.3)', () => {
  it('AC-2: дефолт light при пустом сторадже; нет .dark; стор НЕ перезаписан (нет предпочтения)', () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    )
    expect(screen.getByTestId('theme')).toHaveTextContent('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    // персист только при ЯВНОМ setTheme → пустой стор остаётся «нет предпочтения» (review P3)
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
  })

  it('AC-3: setTheme(dark) вешает .dark + пишет localStorage; setTheme(light) снимает', () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    )
    fireEvent.click(screen.getByText('go-dark'))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')

    fireEvent.click(screen.getByText('go-light'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })

  it('AC-3: инициализация со стора dark → .dark на старте (шов готов к dark)', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    )
    expect(screen.getByTestId('theme')).toHaveTextContent('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('AC-3: useTheme() вне ThemeProvider бросает понятную ошибку', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ThemeProbe />)).toThrow(/useTheme must be used within ThemeProvider/)
    spy.mockRestore()
  })

  it('review P1/P2: устойчив к недоступному localStorage (не роняет App)', () => {
    // storage-blocked окружение: getItem/setItem бросают (private/sandboxed-iframe/policy)
    const getSpy = vi
      .spyOn(Storage.prototype, 'getItem')
      .mockImplementation(() => {
        throw new Error('SecurityError')
      })
    const setSpy = vi
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementation(() => {
        throw new Error('SecurityError')
      })

    // init (читает стор) не должен бросать → фолбэк light, App монтируется
    expect(() =>
      render(
        <ThemeProvider>
          <ThemeProbe />
        </ThemeProvider>,
      ),
    ).not.toThrow()
    expect(screen.getByTestId('theme')).toHaveTextContent('light')
    // setTheme (пишет стор) тоже не роняет
    expect(() => fireEvent.click(screen.getByText('go-dark'))).not.toThrow()

    getSpy.mockRestore()
    setSpy.mockRestore()
  })
})
