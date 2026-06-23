import { apiFetch } from './client'
import type { Attendee, Paginated } from '@/types/attendee'

export interface AttendeeListParams {
  page?: number
  page_size?: number
}

/** GET /api/v1/attendees/ — список участников (envelope). */
export function getAttendees(
  params: AttendeeListParams = {},
): Promise<Paginated<Attendee>> {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiFetch<Paginated<Attendee>>(
    `/api/v1/attendees/${query ? `?${query}` : ''}`,
  )
}
