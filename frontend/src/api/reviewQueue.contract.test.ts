import { describe, expect, it } from 'vitest'

import fixture from './__fixtures__/review-queue.sample.json'
import detailFixture from './__fixtures__/review-queue-detail.sample.json'
import {
  paginatedReviewQueueSchema,
  reviewQueueDetailSchema,
  reviewQueueItemSchema,
} from './reviewQueue.schema'
import { ATTENDEE_STATUSES } from '@/types/status'
import { PROBLEM_FLAGS } from '@/types/problemFlags'

/**
 * Story fe-3.1 (AC-7) — consumer-driven contract-тест zod↔DRF для очереди проверки.
 *
 * Источник формы DTO — backend `ReviewQueueSerializer`; закоммиченная фикстура
 * `__fixtures__/review-queue.sample.json` генерится `manage.py export_review_queue_fixture`
 * (анти-дрейф пинит backend `test_review_queue_contract.py`). Тест НЕ хардкодит форму —
 * валидирует реальную фикстуру схемой. FE-mock для 3.2+ ВЫВОДИТСЯ из этой же фикстуры.
 */
describe('Контракт очереди проверки zod↔DRF (story fe-3.1, AC-7)', () => {
  it('фикстура парсится схемой пагинации (envelope + элементы)', () => {
    expect(() => paginatedReviewQueueSchema.parse(fixture)).not.toThrow()
  })

  it('каждый элемент проходит строгую схему DTO', () => {
    const parsed = paginatedReviewQueueSchema.parse(fixture)
    expect(parsed.results.length).toBeGreaterThan(0)
    for (const item of parsed.results) {
      expect(() => reviewQueueItemSchema.parse(item)).not.toThrow()
    }
  })

  it('status каждого элемента ⊆ ATTENDEE_STATUSES (зеркало state_machine.py)', () => {
    const parsed = paginatedReviewQueueSchema.parse(fixture)
    for (const item of parsed.results) {
      expect(ATTENDEE_STATUSES).toContain(item.status)
    }
  })

  it('problem_flags каждого элемента ⊆ закрытого набора PROBLEM_FLAGS', () => {
    const parsed = paginatedReviewQueueSchema.parse(fixture)
    for (const item of parsed.results) {
      for (const flag of item.problem_flags) {
        expect(PROBLEM_FLAGS).toContain(flag)
      }
    }
  })

  it('nullability: контракт допускает null sub_event_id/sub_event_name (защитно)', () => {
    const parsed = paginatedReviewQueueSchema.parse(fixture)
    // Фикстура содержит элемент с null sub_event (представимость nullable в контракте).
    const hasNullSubEvent = parsed.results.some((i) => i.sub_event_id === null)
    expect(hasNullSubEvent).toBe(true)
  })

  // NEGATIVE — доказывает, что схема имеет «зубы» (ловит дрейф формы/типов).
  it('negative: неизвестный статус → parse бросает', () => {
    const tampered = structuredClone(fixture) as { results: Array<{ status: string }> }
    tampered.results[0].status = '__not_a_status__'
    expect(() => paginatedReviewQueueSchema.parse(tampered)).toThrow()
  })

  it('negative: лишнее поле (дрейф контракта) → strict-схема бросает', () => {
    const tampered = structuredClone(fixture) as { results: Array<Record<string, unknown>> }
    tampered.results[0].unexpected_field = 'drift'
    expect(() => paginatedReviewQueueSchema.parse(tampered)).toThrow()
  })

  it('negative: недопустимый problem_flag → parse бросает', () => {
    const tampered = structuredClone(fixture) as { results: Array<{ problem_flags: string[] }> }
    tampered.results[0].problem_flags = ['__bogus_flag__']
    expect(() => paginatedReviewQueueSchema.parse(tampered)).toThrow()
  })

  it('negative: лишний ключ ENVELOPE (дрейф пагинации) → strict-envelope бросает', () => {
    const tampered = structuredClone(fixture) as Record<string, unknown>
    tampered.total_pages = 7 // ключ, которого нет в StandardResultsSetPagination
    expect(() => paginatedReviewQueueSchema.parse(tampered)).toThrow()
  })
})

describe('Контракт detail-экрана zod↔DRF (story fe-3.3)', () => {
  it('detail-фикстура парсится строгой detail-схемой', () => {
    expect(() => reviewQueueDetailSchema.parse(detailFixture)).not.toThrow()
  })

  it('detail несёт маск-ИИН и НЕ несёт сырой iin', () => {
    const parsed = reviewQueueDetailSchema.parse(detailFixture)
    expect(parsed.iin_masked).toMatch(/^\*{8}\d{4}$/)
    expect((detailFixture as Record<string, unknown>).iin).toBeUndefined()
  })

  it('detail несёт медиа-ключи (URL или null)', () => {
    const parsed = reviewQueueDetailSchema.parse(detailFixture)
    expect('photo' in parsed).toBe(true)
    expect('doc_scan' in parsed).toBe(true)
  })

  it('invariant: в detail-фикстуре нет сырого 12-значного ИИН', () => {
    const blob = JSON.stringify(detailFixture)
    expect(blob.match(/\b\d{12}\b/)).toBeNull()
  })

  // NEGATIVE — detail-схема имеет «зубы».
  it('negative: лишнее поле в detail → strict бросает', () => {
    const tampered = structuredClone(detailFixture) as Record<string, unknown>
    tampered.unexpected_field = 'drift'
    expect(() => reviewQueueDetailSchema.parse(tampered)).toThrow()
  })

  it('negative: сырой iin (дрейф к небезопасному DTO) → strict бросает', () => {
    const tampered = structuredClone(detailFixture) as Record<string, unknown>
    tampered.iin = '851205301234'
    expect(() => reviewQueueDetailSchema.parse(tampered)).toThrow()
  })

  it('negative: неизвестный статус в detail → parse бросает', () => {
    const tampered = structuredClone(detailFixture) as { status: string }
    tampered.status = '__not_a_status__'
    expect(() => reviewQueueDetailSchema.parse(tampered)).toThrow()
  })
})
