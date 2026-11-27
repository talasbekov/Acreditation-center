// ТОЧНЫЙ TypeScript-порт eventproject/validators/iin.py (Story 3.1).
// Намеренный дубликат для real-time feedback (Story 5.2). Любое расхождение с
// Python = баг — алгоритм должен совпадать дословно.
//
// fe-1.4: код-ификация. Возвращаем СТАБИЛЬНЫЕ коды (не ru-строки) — паттерн контракта
// ошибок fe-1.1. Текст рендерит вызывающая сторона: t('validation:'+code, params).
// Алгоритм НЕ менялся — изменилось только возвращаемое значение.

// Коды выровнены с источником правды: eventproject/validators/iin.py + errors/registry.py
// (iin_checksum / iin_date_invalid) — клиент и сервер используют один вокабуляр.
export type IinErrorCode =
  | 'iin_format'
  | 'iin_checksum'
  | 'iin_date_invalid'
  | 'iin_dob_mismatch'

export interface ValidationResult {
  valid: boolean
  /** Стабильный код ошибки (i18n-ключ в namespace `validation`). */
  code?: IinErrorCode
  /** Параметры интерполяции (для iin_dob_mismatch: даты DD.MM.YYYY). */
  params?: Record<string, string>
}

const WEIGHTS_1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
const WEIGHTS_2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
// Позиция 7 ИИН (index 6) → базовый век рождения.
const CENTURY_BASE: Record<number, number> = {
  1: 1800,
  2: 1800,
  3: 1900,
  4: 1900,
  5: 2000,
  6: 2000,
}

function ddmmyyyy(y: number, m: number, d: number): string {
  const pad = (n: number, w: number) => String(n).padStart(w, '0')
  return `${pad(d, 2)}.${pad(m, 2)}.${pad(y, 4)}`
}

/** Строгая проверка календарной даты (JS `Date` ленив → round-trip). */
function isValidDate(y: number, m: number, d: number): boolean {
  if (m < 1 || m > 12 || d < 1 || d > 31) return false
  const dt = new Date(y, m - 1, d)
  return dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d
}

/** Парсит `YYYY-MM-DD` (значение `<input type=date>`) → [y,m,d] или null. */
function parseBirthDate(value: string): [number, number, number] | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim())
  if (!match) return null
  const y = Number(match[1])
  const m = Number(match[2])
  const d = Number(match[3])
  return isValidDate(y, m, d) ? [y, m, d] : null
}

/** Контрольная цифра по первым 11 цифрам; null — если оба прохода дают 10. */
function controlDigit(digits: number[]): number | null {
  let control =
    digits.slice(0, 11).reduce((acc, dig, i) => acc + dig * WEIGHTS_1[i], 0) % 11
  if (control === 10) {
    control =
      digits.slice(0, 11).reduce((acc, dig, i) => acc + dig * WEIGHTS_2[i], 0) % 11
    if (control === 10) return null
  }
  return control
}

/**
 * Валидация казахстанского ИИН: нерезидент → формат → контрольная цифра → дата.
 * @param iin       12 цифр, либо ''/null для нерезидента (→ valid).
 * @param birthDate `YYYY-MM-DD`; пусто/невалидно → сравнение даты пропускается.
 */
export function validateIIN(
  iin: string | null | undefined,
  birthDate: string,
): ValidationResult {
  const normalized = (iin ?? '').trim()
  if (normalized === '') {
    // Нерезидент / ИИН не задан — проверка ИИН не выполняется.
    return { valid: true }
  }
  if (!/^\d{12}$/.test(normalized)) {
    return { valid: false, code: 'iin_format' }
  }

  const digits = normalized.split('').map(Number)

  const control = controlDigit(digits)
  if (control === null || control !== digits[11]) {
    return { valid: false, code: 'iin_checksum' }
  }

  const century = CENTURY_BASE[digits[6]]
  if (century === undefined) {
    return { valid: false, code: 'iin_date_invalid' }
  }
  const year = century + digits[0] * 10 + digits[1]
  const month = digits[2] * 10 + digits[3]
  const day = digits[4] * 10 + digits[5]
  if (!isValidDate(year, month, day)) {
    return { valid: false, code: 'iin_date_invalid' }
  }

  const birth = parseBirthDate(birthDate ?? '')
  if (birth && (birth[0] !== year || birth[1] !== month || birth[2] !== day)) {
    return {
      valid: false,
      code: 'iin_dob_mismatch',
      params: {
        iin_dob: ddmmyyyy(year, month, day),
        entered_dob: ddmmyyyy(birth[0], birth[1], birth[2]),
      },
    }
  }

  return { valid: true }
}
