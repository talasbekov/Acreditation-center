import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import i18n from './i18n'
import { ThemeProvider } from './providers/ThemeProvider'
import './index.css'
import App from './App.tsx'

// retry: false — на 401/403 не ретраим, а сразу редиректим на login (RequireAuth).
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

createRoot(document.getElementById('react-root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </I18nextProvider>
    </QueryClientProvider>
  </StrictMode>,
)
