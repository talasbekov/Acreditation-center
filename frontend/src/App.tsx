import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Toaster } from 'sonner'
import { ensureCsrfCookie } from '@/api/client'
import { RequireAuth } from '@/components/RequireAuth'
import { AppShell } from '@/components/shell/AppShell'
import { AttendeesPage } from '@/pages/AttendeesPage'
import { AddAttendeePage } from '@/pages/AddAttendeePage'
import { EditAttendeePage } from '@/pages/EditAttendeePage'

/**
 * Этап D: прокрутка при переходах. Браузер восстанавливал прежнюю позицию уже после
 * того, как реестр ставил фокус на строку, и уводил экран; карточка открывалась с
 * середины. Теперь каждая страница открывается сверху, реестр сам прокручивает к строке.
 */
function ScrollManager() {
  const { pathname } = useLocation()
  useEffect(() => {
    if ('scrollRestoration' in window.history) window.history.scrollRestoration = 'manual'
  }, [])
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  // P2-8: гарантируем csrftoken cookie до первой мутации (bootstrap при загрузке SPA).
  useEffect(() => {
    void ensureCsrfCookie()
  }, [])

  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <ScrollManager />
      <Toaster richColors position="top-right" />
      <Routes>
        {/* fe-2.2: RequireAuth + AppShell (шапка, переключатель языка, меню по роли) — один
            раз на всё приложение; страницы рендерятся в его <main> через <Outlet/>. */}
        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<AttendeesPage />} />
          <Route path="add" element={<AddAttendeePage />} />
          <Route path="attendees/:id" element={<EditAttendeePage />} />
          {/* catch-all: неизвестные пути → на корень (404-страница — позже) */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
