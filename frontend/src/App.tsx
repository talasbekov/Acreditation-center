import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { ensureCsrfCookie } from '@/api/client'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { RequireAuth } from '@/components/RequireAuth'
import { AttendeesPage } from '@/pages/AttendeesPage'
import { AddAttendeePage } from '@/pages/AddAttendeePage'
import { EditAttendeePage } from '@/pages/EditAttendeePage'

export default function App() {
  const { t } = useTranslation()

  // P2-8: гарантируем csrftoken cookie до первой мутации (bootstrap при загрузке SPA).
  useEffect(() => {
    void ensureCsrfCookie()
  }, [])

  return (
    <BrowserRouter>
      <Toaster richColors position="top-right" />
      {/* fe-1.3: минимальная временная шапка только под LanguageSwitcher.
          Полноценный app-shell + role-filtered nav — fe-2-2; финальное место свитчера — fe-2-3. */}
      <header className="flex items-center justify-between border-b border-neutral-200 px-6 py-3">
        <span className="text-sm font-medium text-neutral-700">{t('nav:app_title')}</span>
        <LanguageSwitcher />
      </header>
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
