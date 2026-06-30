import { describe, it, expect, vi, beforeEach } from 'vitest'

// Мокаем низкоуровневый apiFetch — проверяем сериализацию параметров и применение zod-parse.
const apiFetchMock = vi.fn()
vi.mock('./client', () => ({
  apiFetch: (...a: unknown[]) => apiFetchMock(...a),
}))

import { getReviewQueue } from './reviewQueue'
import fixture from './__fixtures__/review-queue.sample.json'

beforeEach(() => {
  apiFetchMock.mockReset()
})

describe('getReviewQueue (fe-3.2)', () => {
  it('зовёт endpoint очереди и парсит ответ через zod-схему (контракт 3.1)', async () => {
    apiFetchMock.mockResolvedValue(fixture)
    const data = await getReviewQueue({ page: 1, page_size: 50 })
    expect(apiFetchMock).toHaveBeenCalledTimes(1)
    const path = apiFetchMock.mock.calls[0][0] as string
    expect(path.startsWith('/api/v1/review-queue/')).toBe(true)
    // parse вернул валидную форму контракта
    expect(data.count).toBe(3)
    expect(data.results[0].id).toBe(101)
    expect(data.results[0].problem_flags).toContain('no_photo')
  })

  it('сериализует только непустые параметры (page/search/status/sub_event_id/problem)', async () => {
    apiFetchMock.mockResolvedValue(fixture)
    await getReviewQueue({ page: 2, search: 'Алиев', status: 'in_review', sub_event_id: 5, problem: 'no_photo' })
    const path = apiFetchMock.mock.calls[0][0] as string
    const qs = new URLSearchParams(path.split('?')[1])
    expect(qs.get('page')).toBe('2')
    expect(qs.get('search')).toBe('Алиев')
    expect(qs.get('status')).toBe('in_review')
    expect(qs.get('sub_event_id')).toBe('5')
    expect(qs.get('problem')).toBe('no_photo')
  })

  it('пустые/неопределённые параметры не попадают в query', async () => {
    apiFetchMock.mockResolvedValue(fixture)
    await getReviewQueue({ search: '', status: '' })
    const path = apiFetchMock.mock.calls[0][0] as string
    expect(path).toBe('/api/v1/review-queue/')
  })

  it('бросает при дрейфе контракта (лишнее поле → strict-схема падает)', async () => {
    const bad = { ...fixture, results: [{ ...fixture.results[0], unexpected: true }] }
    apiFetchMock.mockResolvedValue(bad)
    await expect(getReviewQueue({})).rejects.toThrow()
  })
})
