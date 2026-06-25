import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

vi.mock('@/lib/csrf', () => ({ getCsrfToken: () => null }))

import { apiFetch, ApiError } from './client'

function mockFetch(status: number, body: unknown, opts: { rejectJson?: boolean } = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status,
      json: opts.rejectJson
        ? () => Promise.reject(new Error('no json'))
        : () => Promise.resolve(body),
    }),
  )
}

describe('apiFetch error message (FE-4)', () => {
  beforeEach(() => vi.unstubAllGlobals())
  afterEach(() => vi.unstubAllGlobals())

  it('не-RFC7807 {detail} → message = detail (а не «HTTP 400»)', async () => {
    mockFetch(400, { detail: 'Дубликат ИИН' })
    await expect(apiFetch('/x')).rejects.toMatchObject({
      status: 400,
      message: 'Дубликат ИИН',
    })
  })

  it('RFC7807 {title} приоритетнее detail (поведение сохранено)', async () => {
    mockFetch(400, { title: 'Заголовок', detail: 'подробности' })
    await expect(apiFetch('/x')).rejects.toMatchObject({ message: 'Заголовок' })
  })

  it('строковое тело ошибки → его текст, не «HTTP»', async () => {
    mockFetch(500, 'Internal boom')
    await expect(apiFetch('/x')).rejects.toMatchObject({ message: 'Internal boom' })
  })

  it('нечитаемое/пустое тело → fallback «HTTP <status>»', async () => {
    mockFetch(503, null, { rejectJson: true })
    await expect(apiFetch('/x')).rejects.toMatchObject({ message: 'HTTP 503' })
  })

  it('problem сохраняется (field) для маппинга в форме', async () => {
    mockFetch(400, { detail: 'Файл велик', field: 'photo' })
    try {
      await apiFetch('/x')
      throw new Error('должно было бросить')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      expect((e as ApiError).problem?.field).toBe('photo')
    }
  })
})
