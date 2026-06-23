import { getCsrfToken } from '@/lib/csrf'

/** RFC 7807 Problem Details — формат ошибок DRF (eventproject/api/exceptions.py). */
export interface ProblemDetail {
  type?: string
  title?: string
  detail?: string
  field?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly problem?: ProblemDetail
  constructor(status: number, message: string, problem?: ProblemDetail) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
  }
}

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

async function safeJson(res: Response): Promise<ProblemDetail | undefined> {
  try {
    return (await res.json()) as ProblemDetail
  } catch {
    return undefined
  }
}

/**
 * Обёртка над fetch для DRF `/api/v1/`.
 * AC-3: session cookie (`credentials: include`) + CSRF-токен в `X-CSRFToken` на unsafe-методах.
 * Бросает ApiError на не-2xx; 401/403 обрабатывает вызывающий (RequireAuth → redirectToLogin).
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)

  if (UNSAFE_METHODS.has(method)) {
    const token = getCsrfToken()
    if (token) headers.set('X-CSRFToken', token)
  }
  // JSON Content-Type только для строкового body — НЕ для FormData/Blob (multipart, Story 5.3).
  if (typeof init.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const res = await fetch(path, {
    ...init,
    method,
    headers,
    credentials: 'include',
  })

  if (!res.ok) {
    const problem = await safeJson(res)
    throw new ApiError(res.status, problem?.title ?? `HTTP ${res.status}`, problem)
  }

  if (res.status === 204) {
    return undefined as T
  }
  return (await res.json()) as T
}
