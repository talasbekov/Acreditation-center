import { describe, it, expect } from 'vitest'
import { pickLocalizedName } from './eventName'

const full = { ru: 'Пресс-центр', kz: 'Баспасөз орталығы', en: 'Press center' }

describe('pickLocalizedName (fe-1.5)', () => {
  it('выбирает имя по активной локали', () => {
    expect(pickLocalizedName(full, 'ru')).toBe('Пресс-центр')
    expect(pickLocalizedName(full, 'kz')).toBe('Баспасөз орталығы')
    expect(pickLocalizedName(full, 'en')).toBe('Press center')
  })

  it('AC3: пустой/NULL kz на kz-локали → fallback на ru', () => {
    expect(pickLocalizedName({ ru: 'Пресс-центр', kz: null, en: null }, 'kz')).toBe('Пресс-центр')
    expect(pickLocalizedName({ ru: 'Пресс-центр', kz: '', en: '' }, 'en')).toBe('Пресс-центр')
  })

  it('всё пусто → fallbackTitle → placeholder', () => {
    expect(pickLocalizedName({ ru: null, kz: null, en: null }, 'kz', 'Титул события')).toBe('Титул события')
    expect(pickLocalizedName({ ru: null, kz: null, en: null }, 'kz')).toBe('—')
  })

  it('names=null → fallbackTitle/placeholder (нет под-события)', () => {
    expect(pickLocalizedName(null, 'kz', 'Титул')).toBe('Титул')
    expect(pickLocalizedName(undefined, 'ru')).toBe('—')
  })

  it('неизвестная локаль → ru', () => {
    expect(pickLocalizedName(full, 'fr')).toBe('Пресс-центр')
  })

  it('регион-квалифицированная локаль → базовый под-тег (en-US→en, ru-RU→ru)', () => {
    // i18n.language может нести регион ('en-US') — берём базовый под-тег, иначе
    // строгое `=== 'en'` не сматчит и англо-локаль тихо упадёт на ru (code-review P1).
    expect(pickLocalizedName(full, 'en-US')).toBe('Press center')
    expect(pickLocalizedName(full, 'en-GB')).toBe('Press center')
    expect(pickLocalizedName(full, 'ru-RU')).toBe('Пресс-центр')
  })
})
