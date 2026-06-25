import { useEffect, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { checkSession } from '@/api/auth'
import { ApiError } from '@/api/client'
import { redirectToLogin } from '@/lib/auth'
import { Button } from '@/components/ui/button'

/**
 * Story 5.1 AC-2: проверяет наличие Django-сессии лёгким authed-запросом.
 * - 401/403 → redirect на /user_login/.
 * - прочие ошибки (500/сеть/CORS) → состояние ошибки с «Повторить» (не застреваем).
 * - успех → рендерит children.
 * FE-3: пробник — `/api/v1/rbac-check/` (checkSession), а не `getAttendees`, чтобы
 * не дублировать загрузку списка участников (AttendeesPage грузит его сам).
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isPending, error, refetch } = useQuery({
    queryKey: ['session-check'],
    queryFn: checkSession,
    retry: false,
  })

  const isAuthError =
    error instanceof ApiError && (error.status === 401 || error.status === 403)

  useEffect(() => {
    if (isAuthError) redirectToLogin()
  }, [isAuthError])

  if (isPending) {
    return <div className="p-6 text-base text-neutral-700">Загрузка…</div>
  }
  if (isAuthError) {
    return (
      <div className="p-6 text-base text-neutral-700">Перенаправление на вход…</div>
    )
  }
  if (error) {
    return (
      <div className="p-6 text-base text-neutral-700">
        <p className="mb-4">
          Не удалось связаться с сервером. Проверьте подключение и повторите.
        </p>
        <Button onClick={() => void refetch()}>Повторить</Button>
      </div>
    )
  }
  return <>{children}</>
}
