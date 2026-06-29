import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

/**
 * Story fe-2.3 — ThemeProvider-ШОВ (light-режим).
 *
 * Весь CSS тёмной темы уже стоит из fe-2.1 (`index.css`: `@custom-variant dark` + `:root` light
 * + `.dark{}` [ASSUMPTION]-stub). Этот провайдер — только React-механизм: вешает/снимает класс
 * `.dark` на `<html>` (architecture §R2) и персистит ЯВНЫЙ выбор. Тёмная тема «оживёт» позже =
 * включить видимый тоггл + утвердить значения, без правки компонентов.
 *
 * ⚠️ Scope fe-2.3: стартовая тема — `light` (или явно сохранённое значение). `prefers-color-scheme`
 * НЕ используется и видимого тоггла НЕТ — отложено до утверждения dark-палитры.
 */
export type Theme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'accreditation.theme'

interface ThemeContextValue {
  theme: Theme
  setTheme: (theme: Theme) => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

function readStoredTheme(): Theme {
  // Значение из localStorage если валидно, иначе 'light'. prefers НЕ читаем (dark отложен).
  // try/catch: getItem бросает в storage-blocked окружении (private/sandboxed-iframe/policy) —
  // тема не должна ронять весь App (провайдер оборачивает <App/>).
  try {
    return localStorage.getItem(THEME_STORAGE_KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme)

  useEffect(() => {
    // `.dark` на <html> (architecture §R2). Изоляция Strangler-Fig сохраняется: токены читают
    // только React-компоненты (legacy Django-шаблоны их не используют). Cleanup снимает класс при
    // размонтировании — не оставляем глобальный `.dark` висеть (встраивание/тесты).
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    return () => root.classList.remove('dark')
  }, [theme])

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    // Персист ТОЛЬКО при явном выборе (не на старте) → пустой стор остаётся «нет предпочтения»,
    // будущий prefers-color-scheme-дефолт не перетирается. try/catch: setItem бросает на
    // quota/security — тема всё равно применяется в рамках сессии.
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      /* storage недоступен — деградируем мягко (тема живёт в памяти до перезагрузки) */
    }
  }, [])

  const value = useMemo<ThemeContextValue>(() => ({ theme, setTheme }), [theme, setTheme])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
