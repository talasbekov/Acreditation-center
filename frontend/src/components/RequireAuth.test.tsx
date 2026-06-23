import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiError } from '@/api/client'

// Нет сессии: authed-запрос отклоняется с 401.
vi.mock('@/api/attendees', () => ({
  getAttendees: vi.fn(() => Promise.reject(new ApiError(401, 'Не аутентифицирован'))),
}))
vi.mock('@/lib/auth', () => ({
  redirectToLogin: vi.fn(),
}))

import { RequireAuth } from './RequireAuth'
import { redirectToLogin } from '@/lib/auth'

function renderGuard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <RequireAuth>
        <div>секретное содержимое</div>
      </RequireAuth>
    </QueryClientProvider>,
  )
}

describe('RequireAuth (AC-2)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('редиректит на /user_login/ при отсутствии сессии (401)', async () => {
    renderGuard()
    await waitFor(() => expect(redirectToLogin).toHaveBeenCalledTimes(1))
  })

  it('не показывает защищённое содержимое без сессии', async () => {
    renderGuard()
    await waitFor(() => expect(redirectToLogin).toHaveBeenCalled())
    expect(screen.queryByText('секретное содержимое')).not.toBeInTheDocument()
  })
})
