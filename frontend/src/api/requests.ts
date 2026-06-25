import { apiFetch } from './client'
import type { Paginated } from '@/types/attendee'

/** Строка `/api/v1/requests/` — RBAC-scoped Request («категория») для селектора (FE-1).
 *  `Attendee.request` — FK на Request; форма выбирает его из списка вместо ручного PK. */
export interface RequestOption {
  id: number
  name: string
  event_id: number
  event_name: string
}

/** GET /api/v1/requests/ — RBAC-scoped список Request оператора (для `<select>`). */
export async function getRequests(): Promise<RequestOption[]> {
  const data = await apiFetch<Paginated<RequestOption>>(
    '/api/v1/requests/?page_size=500',
  )
  // Резильентность: при неожиданном теле (ошибка/edge) — пустой список, не throw.
  return Array.isArray(data?.results) ? data.results : []
}
