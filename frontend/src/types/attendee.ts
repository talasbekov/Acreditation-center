// Контракт данных выровнен по AttendeeViewSet (Story 3.4) + AttendeeListSerializer (5.5).

/** Envelope-пагинация DRF (`StandardResultsSetPagination`, retro Epic 2). */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

/** Строка списка (`GET /api/v1/attendees/`) — AttendeeListSerializer (Story 5.5).
 *  ИИН маскирован (`iin_masked`, последние 4); полного `iin` в списке нет. */
export interface Attendee {
  id: number
  surname: string
  firstname: string
  patronymic: string | null
  status: string
  category: number | null
  dateAdd: string
  iin_masked: string
  /** Story fe-3.7: причина/счётчик последнего возврата (инбокс). «Возвращена» = return_count>0. */
  last_return_reason: string | null
  return_count: number
}

/** Detail (`GET /api/v1/attendees/{id}/`) — полный AttendeeSerializer (для edit, 5.5). */
export interface AttendeeDetail {
  id: number
  surname: string
  firstname: string
  patronymic: string | null
  birthDate: string | null
  countryId: string
  iin: string | null
  request: number
  status: string
  /** P2-7: URL загруженного фото/документа (для превью в edit). */
  photo: string | null
  docScan: string | null
  /** Story fe-3.7: причина/счётчик возврата — баннер на EditAttendeePage при return_count>0. */
  last_return_reason: string | null
  return_count: number
}
