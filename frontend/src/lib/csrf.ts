/** Читает значение cookie по имени (для Django `csrftoken`/`sessionid`). */
export function getCookie(name: string): string | null {
  const cookies = document.cookie ? document.cookie.split('; ') : []
  for (const cookie of cookies) {
    const eq = cookie.indexOf('=')
    const key = eq === -1 ? cookie : cookie.slice(0, eq)
    if (key === name) {
      return decodeURIComponent(eq === -1 ? '' : cookie.slice(eq + 1))
    }
  }
  return null
}

/** CSRF-токен Django из cookie (отправляется в заголовке `X-CSRFToken`). */
export function getCsrfToken(): string | null {
  return getCookie('csrftoken')
}
