import { apiFetch } from './client'
import {
  paginatedReviewQueueSchema,
  reviewQueueDetailSchema,
  type PaginatedReviewQueue,
  type ReviewQueueDetail,
} from './reviewQueue.schema'

/**
 * Story fe-3.2 — клиент очереди проверки. Зеркало `attendees.ts::getAttendees`.
 * Контракт DTO заморожен в fe-3.1 (`reviewQueue.schema.ts`) — здесь не переопределяем.
 *
 * Поведение backend (fe-3.1): `?status=` сужает очередь (только submitted|in_review),
 * `?sub_event_id=` фильтрует по leaf-Event, `?problem=` — по закрытому enum, `?search=` —
 * по ФИО. Пустой/невалидный параметр → 400 (coded_error). Пустую строку НЕ отправляем.
 */
export interface ReviewQueueParams {
  page?: number
  page_size?: number
  search?: string
  status?: string
  sub_event_id?: number
  problem?: string
}

/** GET /api/v1/review-queue/ — очередь «На проверке» (envelope, page_size 50). */
export async function getReviewQueue(
  params: ReviewQueueParams = {},
): Promise<PaginatedReviewQueue> {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  if (params.search) qs.set('search', params.search)
  if (params.status) qs.set('status', params.status)
  if (params.sub_event_id) qs.set('sub_event_id', String(params.sub_event_id))
  if (params.problem) qs.set('problem', params.problem)
  const query = qs.toString()
  const raw = await apiFetch<unknown>(
    `/api/v1/review-queue/${query ? `?${query}` : ''}`,
  )
  // Рантайм-страховка замороженного контракта (.strict() ловит дрейф ключей/типов).
  return paginatedReviewQueueSchema.parse(raw)
}

/** fe-3.3 — GET /api/v1/review-queue/{id}/ — DTO экрана деталей (маск-ИИН + медиа). */
export async function getReviewQueueItem(id: number): Promise<ReviewQueueDetail> {
  const raw = await apiFetch<unknown>(`/api/v1/review-queue/${id}/`)
  return reviewQueueDetailSchema.parse(raw)
}

/**
 * fe-3.4 — одобрение заявки (in_review → ready). Решение проверяющего на
 * `AttendeeViewSet` (не review-queue): `POST /api/v1/attendees/{id}/approve/`.
 * Ответ — masked-safe `{id, status}` (НЕ часть DTO-контракта очереди fe-3.1, поэтому
 * без zod-strict — не рендерится как контракт). Не-«На проверке» → 409 (машинный код
 * `status_transition_invalid` в конверте fe-1.1 → ApiError.problem → FE-маппер fe-1.2).
 */
export interface ApproveResult {
  id: number
  status: string
}

export async function approveReviewQueueItem(id: number): Promise<ApproveResult> {
  return apiFetch<ApproveResult>(`/api/v1/attendees/${id}/approve/`, {
    method: 'POST',
  })
}

/**
 * fe-3.5 — возврат заявки оператору с обязательной причиной (in_review → submitted).
 * `POST /api/v1/attendees/{id}/return/` `{reason}`. Ответ masked-safe `{id, status}` (как
 * approve — реш.#6, не контракт-DTO, без zod-strict). Не-«На проверке» → 409
 * (`status_transition_invalid`); пустой reason → 400 (`required`/`reason`) — оба в конверте
 * fe-1.1 → ApiError.problem → FE-маппер fe-1.2.
 */
export async function returnReviewQueueItem(
  id: number,
  reason: string,
): Promise<ApproveResult> {
  return apiFetch<ApproveResult>(`/api/v1/attendees/${id}/return/`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}
