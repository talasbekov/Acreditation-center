import { z } from 'zod'

import { ATTENDEE_STATUSES } from '@/types/status'
import { PROBLEM_FLAGS } from '@/types/problemFlags'

// fe-1.5 — трилингв-триплет имени под-события (nullable-safe: null когда нет request).
// Аддитивно к frozen `sub_event_name` (ru/legacy fallback). React выбирает по активной локали
// (pickLocalizedName); сервер не локализует. Поля nullable — листовые события часто без kz/en.
const subEventNamesSchema = z
  .object({
    ru: z.string().nullable(),
    kz: z.string().nullable(),
    en: z.string().nullable(),
  })
  .nullable()

/**
 * Story fe-3.1 — zod-схема DTO очереди проверки (замороженный контракт 3.2-3.7).
 *
 * Источник истины формы — backend `ReviewQueueSerializer`; FE-mock ВЫВОДИТСЯ из
 * `__fixtures__/review-queue.sample.json` (генерит `manage.py export_review_queue_fixture`,
 * анти-дрейф пинит backend-тест `test_review_queue_contract.py`). `.strict()` → лишнее
 * поле = дрейф (negative-тест). Nullability: sub_event_id/sub_event_name/last_return_reason.
 *
 * zod v4: `z.enum(readonly tuple)` ок; `.strict()` запрещает неизвестные ключи.
 */
export const reviewQueueItemSchema = z
  .object({
    id: z.number(),
    full_name: z.string(),
    iin_masked: z.string(),
    status: z.enum(ATTENDEE_STATUSES),
    sub_event_id: z.number().nullable(),
    sub_event_name: z.string().nullable(),
    sub_event_names: subEventNamesSchema,
    problem_flags: z.array(z.enum(PROBLEM_FLAGS)),
    last_return_reason: z.string().nullable(),
    return_count: z.number(),
  })
  .strict()

export const paginatedReviewQueueSchema = z
  .object({
    count: z.number(),
    next: z.string().nullable(),
    previous: z.string().nullable(),
    results: z.array(reviewQueueItemSchema),
  })
  .strict()

/**
 * Story fe-3.3 — zod-схема DTO ЭКРАНА ДЕТАЛЕЙ (`GET /api/v1/review-queue/{id}/`).
 *
 * Отдельная strict-схема (не ослабляем замороженную `reviewQueueItemSchema`): тонкий
 * DTO списка + медиа/identity-поля от backend `ReviewQueueDetailSerializer`. Источник
 * формы — `__fixtures__/review-queue-detail.sample.json` (генерит та же export-команда;
 * анти-дрейф пинит backend `test_review_queue_contract.py`). ИИН — `iin_masked` (сырого
 * нет). `photo`/`doc_scan` — protected /media/ URL или null (явный placeholder в UI).
 */
export const reviewQueueDetailSchema = z
  .object({
    id: z.number(),
    full_name: z.string(),
    iin_masked: z.string(),
    status: z.enum(ATTENDEE_STATUSES),
    sub_event_id: z.number().nullable(),
    sub_event_name: z.string().nullable(),
    sub_event_names: subEventNamesSchema,
    problem_flags: z.array(z.enum(PROBLEM_FLAGS)),
    last_return_reason: z.string().nullable(),
    return_count: z.number(),
    photo: z.string().nullable(),
    doc_scan: z.string().nullable(),
    birth_date: z.string().nullable(),
    is_resident: z.boolean(),
    country: z.string(),
    post: z.string(),
    transcription: z.string(),
    doc_type: z.string(),
    created_at: z.string().nullable(),
  })
  .strict()

export type ReviewQueueItem = z.infer<typeof reviewQueueItemSchema>
export type PaginatedReviewQueue = z.infer<typeof paginatedReviewQueueSchema>
export type ReviewQueueDetail = z.infer<typeof reviewQueueDetailSchema>
