import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { RequireAuth } from '@/components/RequireAuth'
import { AttendeesPage } from '@/pages/AttendeesPage'
import { AddAttendeePage } from '@/pages/AddAttendeePage'

export default function App() {
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
        {/* catch-all: неизвестные пути → на корень (bootstrap; 404-страница — позже) */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
