import { describe, it, expect, beforeEach } from 'vitest'
import { getCookie, getCsrfToken } from './csrf'

function clearCookies() {
  for (const c of document.cookie.split(';')) {
    const name = c.split('=')[0].trim()
    if (name) {
      document.cookie = `${name}=;expires=${new Date(0).toUTCString()};path=/`
    }
  }
}

describe('csrf', () => {
  beforeEach(clearCookies)

  it('возвращает null, если csrftoken отсутствует', () => {
    expect(getCsrfToken()).toBeNull()
  })

  it('читает csrftoken из cookie', () => {
    document.cookie = 'csrftoken=abc123'
    expect(getCsrfToken()).toBe('abc123')
  })

  it('getCookie читает произвольную cookie среди нескольких', () => {
    document.cookie = 'sessionid=xyz'
    document.cookie = 'csrftoken=tok'
    expect(getCookie('sessionid')).toBe('xyz')
    expect(getCookie('csrftoken')).toBe('tok')
    expect(getCookie('missing')).toBeNull()
  })
})
