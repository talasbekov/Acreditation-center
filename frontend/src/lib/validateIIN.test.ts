import { describe, it, expect } from 'vitest'
import { validateIIN } from './validateIIN'

// Векторы выведены по самому алгоритму (см. validateIIN.ts / iin.py).
// "900515312349" + 1990-05-15: первый проход контрольной цифры = 9.
// "950320300804" + 1995-03-20: первый проход = 10 → второй проход = 4 (ветка WEIGHTS_2).
// "000229500008" + 2000-02-29: високосный год.

describe('validateIIN — порт iin.py (Story 5.2 AC-1/AC-5)', () => {
  it('1. корректный ИИН + дата → valid', () => {
    expect(validateIIN('900515312349', '1990-05-15')).toEqual({ valid: true })
  })

  it('2. контрольная цифра через второй проход (остаток 10) → valid', () => {
    expect(validateIIN('950320300804', '1995-03-20')).toEqual({ valid: true })
  })

  it('3. високосная граница 29 февраля → valid', () => {
    expect(validateIIN('000229500008', '2000-02-29')).toEqual({ valid: true })
  })

  it('4. несовпадение даты → ошибка с DD.MM.YYYY', () => {
    const r = validateIIN('900515312349', '1990-05-16')
    expect(r.valid).toBe(false)
    expect(r.error).toContain('15.05.1990')
    expect(r.error).toContain('16.05.1990')
    expect(r.error).toContain('не совпадает')
  })

  it('5. неверная контрольная цифра', () => {
    expect(validateIIN('900515312340', '1990-05-15')).toEqual({
      valid: false,
      error: 'ИИН некорректен: неверная контрольная цифра.',
    })
  })

  it('6. длина не 12 → формат', () => {
    expect(validateIIN('12345', '1990-05-15')).toEqual({
      valid: false,
      error: 'ИИН должен содержать ровно 12 цифр.',
    })
  })

  it('7. нецифровой символ → формат', () => {
    expect(validateIIN('90051531234x', '1990-05-15')).toEqual({
      valid: false,
      error: 'ИИН должен содержать ровно 12 цифр.',
    })
  })

  it('8. нерезидент: пустая строка → valid (проверка не выполняется)', () => {
    expect(validateIIN('', '1990-05-15')).toEqual({ valid: true })
  })

  it('9. нерезидент: null/undefined → valid', () => {
    expect(validateIIN(null, '1990-05-15')).toEqual({ valid: true })
    expect(validateIIN(undefined, '1990-05-15')).toEqual({ valid: true })
  })

  it('10. недопустимая дата в ИИН (30 февраля) → дата невалидна', () => {
    expect(validateIIN('900230312349', '1990-02-28')).toEqual({
      valid: false,
      error: 'ИИН некорректен: недопустимая дата рождения.',
    })
  })

  it('11. позиция 7 вне диапазона 1–6 → дата невалидна', () => {
    expect(validateIIN('900515712344', '1990-05-15')).toEqual({
      valid: false,
      error: 'ИИН некорректен: недопустимая дата рождения.',
    })
  })

  it('12. ИИН валиден без введённой даты (сравнение пропускается)', () => {
    expect(validateIIN('900515312349', '')).toEqual({ valid: true })
  })
})
