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
  /** Этап C: черновик, возвращённый проверяющим (причина — только в detail). */
  returned?: boolean
  /** Этап D: контекст строки — номер заявки и мероприятие. */
  request_name?: string
  event_name?: string
  /** Story fe-3.7: сколько раз участника возвращали. */
  return_count?: number
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
  /** Этап D: остальные поля формы (как у HTML-формы). */
  transcription?: string
  sexId?: string
  post?: string
  stickId?: string
  docTypeId?: string
  docSeries?: string
  docNumber?: string | null
  docBegin?: string | null
  docEnd?: string | null
  docIssue?: string
  visitObjects?: string
  /** P2-7: URL загруженного фото/документа (для превью в edit). */
  photo: string | null
  docScan: string | null
  /** Этап C: причина возврата от проверяющего (пусто, если не возвращали). */
  review_comment?: string
  /** Story fe-3.7: последняя причина возврата (ИИН скрыт) и счётчик возвратов. */
  last_return_reason?: string | null
  return_count?: number
}
