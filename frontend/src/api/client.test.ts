import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiFetch, ApiError } from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function headersOf(call: unknown): Headers {
  return (call as [string, RequestInit])[1].headers as Headers
}

describe('apiFetch — session/CSRF (AC-3)', () => {
  beforeEach(() => {
    document.cookie = 'csrftoken=tok42'
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GET: credentials=include и БЕЗ X-CSRFToken', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/v1/attendees/')

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.credentials).toBe('include')
    expect(headersOf(fetchMock.mock.calls[0]).get('X-CSRFToken')).toBeNull()
  })

  it('POST: ставит X-CSRFToken из cookie', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 1 }, 201))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/api/v1/attendees/', { method: 'POST', body: '{}' })

    expect(headersOf(fetchMock.mock.calls[0]).get('X-CSRFToken')).toBe('tok42')
  })

  it('бросает ApiError с RFC7807 на 400', async () => {
    const problem = { type: 'about:blank', title: 'Ошибка валидации', field: 'iin' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(problem, 400)))

    await expect(
      apiFetch('/api/v1/attendees/', { method: 'POST', body: '{}' }),
    ).rejects.toMatchObject({ status: 400 })
  })

  it('ApiError содержит status и problem', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ title: 'Нет доступа' }, 403)),
    )
    try {
      await apiFetch('/api/v1/attendees/')
      expect.unreachable('должно было бросить')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      expect((e as ApiError).status).toBe(403)
      expect((e as ApiError).problem?.title).toBe('Нет доступа')
    }
  })
})
