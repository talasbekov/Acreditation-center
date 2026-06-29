import { useQuery } from '@tanstack/react-query'
import { checkSession } from '@/api/auth'

/**
 * Story fe-2.2 (AC-2) — роль текущего пользователя для role-filtered навигации.
 *
 * ⭐ Переиспользует queryKey `['session-check']` (тот же, что в RequireAuth) → React Query
 * возвращает уже закэшированный ответ `checkSession()` (`GET /api/v1/rbac-check/`). Второго
 * сетевого запроса нет. Эндпоинта `/api/v1/me` в проекте НЕТ — не изобретаем его, роль НЕ
 * берётся из URL/клиента (это контур безопасности; реальное разграничение — на бэкенде).
 *
 * Пока запрос не разрешён / ошибка → `undefined` (nav рендерит минимум; RequireAuth уже
 * обрабатывает pending/401/403/ошибку выше по дереву).
 */
export function useRole(): string | undefined {
  const { data } = useQuery({
    queryKey: ['session-check'],
    queryFn: checkSession,
    retry: false,
    // Роль не меняется в рамках сессии → данные «свежие» навсегда. Без этого (staleTime
    // дефолт 0) монтирование observer'а useRole ПОСЛЕ RequireAuth триггерит refetchOnMount
    // → второй GET /api/v1/rbac-check/. С Infinity второй запрос не уходит (та же гарантия,
    // что AC-2). Истечение сессии всё равно ловится 401 на реальных запросах.
    staleTime: Infinity,
  })
  return data?.role
}
