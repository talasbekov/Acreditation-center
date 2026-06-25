// Story 5.1 AC-2: session-based auth — при отсутствии сессии редирект на Django login.
// P2-9: пробрасываем `next` (текущий путь) — `user_login` теперь возвращает на него
// после входа (safe-redirect: только этот хост). Возврат в SPA после Django-логина.
const LOGIN_PATH = '/user_login/'

export function redirectToLogin(): void {
  const next = window.location.pathname + window.location.search
  window.location.assign(`${LOGIN_PATH}?next=${encodeURIComponent(next)}`)
}
