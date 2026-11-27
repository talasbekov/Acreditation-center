import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Toaster } from 'sonner'
import { ensureCsrfCookie } from '@/api/client'
import { RequireAuth } from '@/components/RequireAuth'
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
        <Route
          path="/"
          element={
            <RequireAuth>
              <AttendeesPage />
            </RequireAuth>
          }
        />
        <Route
          path="/add"
          element={
            <RequireAuth>
              <AddAttendeePage />
            </RequireAuth>
          }
        />
        <Route
          path="/attendees/:id"
          element={
            <RequireAuth>
              <EditAttendeePage />
            </RequireAuth>
          }
        />
        {/* catch-all: неизвестные пути → на корень (bootstrap; 404-страница — позже) */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
