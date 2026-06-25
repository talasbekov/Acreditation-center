import { apiFetch } from './client'

/** FE-3: лёгкая проверка сессии через назначенный auth-пробник `/api/v1/rbac-check/`
 *  вместо `getAttendees({page_size:1})` — убирает двойной fetch списка участников
 *  на первой загрузке (RequireAuth + AttendeesPage больше не дублируют /attendees/). */
export function checkSession(): Promise<{ role: string }> {
  return apiFetch<{ role: string }>('/api/v1/rbac-check/')
}
