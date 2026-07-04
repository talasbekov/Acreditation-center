// design-sync preview support — НЕ код приложения. Обёртка для превью-карточек:
// i18n (side-effect init), React Query, Router (NavLink/Outlet в AppShell), ThemeProvider.
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../frontend/src/providers/ThemeProvider'
import '../../frontend/src/i18n'

// retry:false — в превью нет бэкенда; запросы (useRole/requests) молча падают и UI
// рендерит минимальное состояние, не зависая на ретраях.
const client = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
})

export function DSPreviewProvider({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ThemeProvider>{children}</ThemeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}
