import { apiFetch } from './client'
import type { Attendee, AttendeeDetail, Paginated } from '@/types/attendee'

export interface AttendeeListParams {
  page?: number
  page_size?: number
  search?: string
  status?: string
  category_id?: number
  /** Story fe-3.7: инбокс возвратов — только возвращённые (submitted + return_count>0). */
  returned?: boolean
}

/** GET /api/v1/attendees/ — список участников (envelope). Story 3.4 + 5.5. */
export function getAttendees(
  params: AttendeeListParams = {},
): Promise<Paginated<Attendee>> {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  if (params.search) qs.set('search', params.search)
  if (params.status) qs.set('status', params.status)
  if (params.category_id) qs.set('category_id', String(params.category_id))
  if (params.returned) qs.set('returned', 'true')
  const query = qs.toString()
  return apiFetch<Paginated<Attendee>>(
    `/api/v1/attendees/${query ? `?${query}` : ''}`,
  )
}

/** GET /api/v1/attendees/{id}/ — полные данные участника (для редактирования). Story 5.5. */
export function getAttendee(id: number): Promise<AttendeeDetail> {
  return apiFetch<AttendeeDetail>(`/api/v1/attendees/${id}/`)
}
