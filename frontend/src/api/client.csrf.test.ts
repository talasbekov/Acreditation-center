import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const getCsrfTokenMock = vi.fn()
vi.mock('@/lib/csrf', () => ({
  getCsrfToken: () => getCsrfTokenMock(),
}))

import { ensureCsrfCookie } from './client'

describe('ensureCsrfCookie (P2-8)', () => {
  beforeEach(() => {
    getCsrfTokenMock.mockReset()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('запрашивает /api/v1/csrf/, когда cookie ещё нет', async () => {
    getCsrfTokenMock.mockReturnValue(null)
    await ensureCsrfCookie()
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/csrf/',
      expect.objectContaining({ credentials: 'include' }),
    )
  })

  it('ничего не запрашивает, если cookie уже есть', async () => {
    getCsrfTokenMock.mockReturnValue('existing-token')
    await ensureCsrfCookie()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('best-effort: сетевая ошибка не пробрасывается', async () => {
    getCsrfTokenMock.mockReturnValue(null)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
    await expect(ensureCsrfCookie()).resolves.toBeUndefined()
  })
})
