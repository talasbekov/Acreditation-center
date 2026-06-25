import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { ensureCsrfCookie } from '@/api/client'
import { RequireAuth } from '@/components/RequireAuth'
import { AttendeesPage } from '@/pages/AttendeesPage'
import { AddAttendeePage } from '@/pages/AddAttendeePage'
import { EditAttendeePage } from '@/pages/EditAttendeePage'

export default function App() {
  // P2-8: гарантируем csrftoken cookie до первой мутации (bootstrap при загрузке SPA).
  useEffect(() => {
    void ensureCsrfCookie()
  }, [])

  return (
    <BrowserRouter>
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
