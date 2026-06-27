import { getCsrfToken } from '@/lib/csrf'

/** RFC 7807 Problem Details — формат ошибок DRF (eventproject/api/exceptions.py). */
export interface ProblemDetail {
  type?: string
  title?: string
  detail?: string
  field?: string
  // fe-1.2: новое поле `params` — машинный `type` (объявлен выше, с fe-1.1) несёт их
  // для интерполяции i18n (`t('errors:'+type, params)`). Рантайм уже сохранял params
  // (asProblem кастит всё тело DRF-ответа) — здесь только объявление поля в типе.
  params?: Record<string, unknown>
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

async function safeJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    return undefined
  }
}

/** Плоский объект-ошибка (RFC7807 или DRF `{detail}`/field-errors) — для `.field`/`.detail`. */
function asProblem(body: unknown): ProblemDetail | undefined {
  return body !== null && typeof body === 'object' && !Array.isArray(body)
    ? (body as ProblemDetail)
    : undefined
}

/** FE-4: не-RFC7807 тело тоже несёт текст. Приоритет: title → detail → строковое
 *  тело → fallback `HTTP <status>` (раньше всё, кроме title, схлопывалось в HTTP). */
function errorMessage(body: unknown, status: number): string {
  if (typeof body === 'string' && body.trim()) return body
  const p = asProblem(body)
  const text = p?.title ?? p?.detail
  if (typeof text === 'string' && text.trim()) return text
  return `HTTP ${status}`
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
    const body = await safeJson(res)
    throw new ApiError(res.status, errorMessage(body, res.status), asProblem(body))
  }

  if (res.status === 204) {
    return undefined as T
  }
  return (await res.json()) as T
}

/**
 * P2-8: гарантирует наличие `csrftoken` cookie до первой мутации. В штатном потоке
 * cookie ставит Django-страница логина; этот bootstrap страхует случаи, когда SPA
 * открыт с сессией, но без csrftoken (иначе первый POST уйдёт без X-CSRFToken → 403).
 * Best-effort: сетевые ошибки не блокируют загрузку SPA.
 */
export async function ensureCsrfCookie(): Promise<void> {
  if (getCsrfToken()) return
  try {
    await fetch('/api/v1/csrf/', { credentials: 'include' })
  } catch {
    // ignore — повторная попытка произойдёт при следующем вызове
  }
}
