// Story 5.1 AC-2: session-based auth — при отсутствии сессии редирект на Django login.
// Прим. (code-review 2026-06-23): Django-вью `user_login` НЕ поддерживает `?next=`
// (после входа кидает на legacy /application/ или /avmac/), поэтому `next` не передаём —
// иначе это вводит в заблуждение. Возврат в SPA после логина — отдельная задача (deferred-work).
const LOGIN_PATH = '/user_login/'

export function redirectToLogin(): void {
  window.location.assign(LOGIN_PATH)
}
