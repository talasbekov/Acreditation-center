// Контракт данных выровнен по docs/integration-spec-v1.md (Story 4.1) и AttendeeViewSet (Story 3.4).
// Для bootstrap — минимальный набор полей; расширяется в 5.2–5.5.

/** Envelope-пагинация DRF (`StandardResultsSetPagination`, retro Epic 2). */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface Attendee {
  id: number
  lastName: string
  firstName: string
  status: string
}
