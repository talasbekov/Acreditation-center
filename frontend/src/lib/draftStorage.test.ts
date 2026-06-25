import { describe, it, expect, afterEach, vi } from 'vitest'
import {
  DRAFT_KEY,
  saveDraft,
  loadDraft,
  clearDraft,
  hasDraft,
  isMeaningfulDraft,
} from './draftStorage'

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('draftStorage (Story 5.4)', () => {
  it('save → load round-trip только текстовых полей', () => {
    saveDraft({ surname: 'Тестов', firstname: 'Тест', request: '5' })
    expect(loadDraft()).toEqual({ surname: 'Тестов', firstname: 'Тест', request: '5' })
  })

  it('photo/docScan (File) НЕ попадают в черновик', () => {
    const file = new File([new Uint8Array([1])], 'p.jpg', { type: 'image/jpeg' })
    saveDraft({ surname: 'A', photo: file, docScan: file })
    const stored = loadDraft()
    expect(stored).toEqual({ surname: 'A' })
    expect(stored).not.toHaveProperty('photo')
    expect(stored).not.toHaveProperty('docScan')
  })

  it('load при отсутствии черновика → null', () => {
    expect(loadDraft()).toBeNull()
  })

  it('битый JSON → null и мусор удалён', () => {
    localStorage.setItem(DRAFT_KEY, '{не json')
    expect(loadDraft()).toBeNull()
    expect(localStorage.getItem(DRAFT_KEY)).toBeNull()
  })

  it('loadDraft отбрасывает не-строковые/неизвестные поля (анти-краш restore)', () => {
    localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({ surname: 'A', iin: 12345, extra: { x: 1 }, request: ['7'] }),
    )
    expect(loadDraft()).toEqual({ surname: 'A' })
  })

  it('loadDraft на JSON-массиве → null', () => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify([1, 2, 3]))
    expect(loadDraft()).toBeNull()
  })

  it('clearDraft удаляет черновик', () => {
    saveDraft({ surname: 'A' })
    clearDraft()
    expect(loadDraft()).toBeNull()
  })

  it('hasDraft: true только при значимом непустом значении', () => {
    expect(hasDraft()).toBe(false)
    saveDraft({ countryId: '1000000105' }) // только дефолтная страна → не значимо
    expect(hasDraft()).toBe(false)
    saveDraft({ surname: 'Тестов' })
    expect(hasDraft()).toBe(true)
  })

  it('isMeaningfulDraft игнорирует пустые/пробельные значения', () => {
    expect(isMeaningfulDraft({ surname: '   ', request: '' })).toBe(false)
    expect(isMeaningfulDraft({ request: '5' })).toBe(true)
  })

  it('saveDraft не бросает при недоступном localStorage (best-effort)', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceeded')
    })
    expect(() => saveDraft({ surname: 'A' })).not.toThrow()
  })
})
