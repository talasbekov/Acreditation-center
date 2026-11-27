import { afterEach, describe, expect, it, vi } from 'vitest'
import { removeLegacyAttendeeDraft } from './draftStorage'

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('удаление старого черновика', () => {
  it('удаляет только старый ключ и не читает его содержимое', () => {
    localStorage.setItem('attendee_draft_v1', 'invalid JSON')
    localStorage.setItem('preference', 'dark')
    const read = vi.spyOn(Storage.prototype, 'getItem')
    removeLegacyAttendeeDraft()
    removeLegacyAttendeeDraft()
    expect(read).not.toHaveBeenCalled()
    expect(localStorage.getItem('attendee_draft_v1')).toBeNull()
    expect(localStorage.getItem('preference')).toBe('dark')
  })

  it('запрет доступа к хранилищу не блокирует приложение', () => {
    vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new DOMException('Storage disabled', 'SecurityError')
    })
    expect(removeLegacyAttendeeDraft).not.toThrow()
  })
})
