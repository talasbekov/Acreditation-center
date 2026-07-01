import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { ensureCsrfCookie } from '@/api/client'
import { RequireAuth } from '@/components/RequireAuth'
import { AppShell } from '@/components/shell/AppShell'
import { AttendeesPage } from '@/pages/AttendeesPage'
import { AddAttendeePage } from '@/pages/AddAttendeePage'
import { EditAttendeePage } from '@/pages/EditAttendeePage'
import { ReviewQueuePage } from '@/pages/ReviewQueuePage'
import { ApplicationDetailPage } from '@/pages/ApplicationDetailPage'
import { ReturnsInboxPage } from '@/pages/ReturnsInboxPage'

export default function App() {
  // P2-8: гарантируем csrftoken cookie до первой мутации (bootstrap при загрузке SPA).
  useEffect(() => {
    void ensureCsrfCookie()
  }, [])

  return (
    <BrowserRouter>
      <Toaster richColors position="top-right" />
      <Routes>
        {/* fe-2.2: layout-route — RequireAuth + AppShell оборачивают всё приложение ОДИН раз;
            страницы рендерятся в <main> через <Outlet/>. role-filtered nav + skip-link + лендмарки. */}
        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<AttendeesPage />} />
          <Route path="queue" element={<ReviewQueuePage />} />
          {/* fe-3.3: detail заявки очереди — открывается из строки очереди (fe-3.2). */}
          <Route path="queue/:id" element={<ApplicationDetailPage />} />
          <Route path="add" element={<AddAttendeePage />} />
          <Route path="attendees/:id" element={<EditAttendeePage />} />
          {/* fe-3.7: инбокс возвратов оператора (nav:notifications; Notifications отложены). */}
          <Route path="notifications" element={<ReturnsInboxPage />} />
          {/* catch-all: неизвестные пути → на корень (404-страница — позже) */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
