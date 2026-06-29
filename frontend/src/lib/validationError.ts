// Story fe-1.4: zod/validateIIN сообщения — машинные i18n-ключи (паттерн контракта
// ошибок fe-1.1), а не ru-проза. react-hook-form несёт в `error.message` только строку,
// поэтому ключ с параметрами (iin_dob_mismatch) кодируем как JSON; форма декодирует и
// переводит через t(key, params). Серверные ошибки (setError из mapApiError) кладут уже
// готовый локализованный текст — translateFieldError возвращает его как есть.

export interface EncodedError {
  key: string
  params?: Record<string, string>
}

/** Кодирует i18n-ключ (+опц. params) в строку сообщения для zod/RHF. */
export function encodeValidationError(
  key: string,
  params?: Record<string, string>,
): string {
  return params ? JSON.stringify({ key, params }) : key
}

type Translate = (key: string, params?: Record<string, unknown>) => string

/**
 * Переводит сообщение об ошибке поля.
 * - JSON `{key, params}` → t(key, params) (ключи с интерполяцией).
 * - `validation:...` (или иной ns-ключ) → t(key).
 * - всё прочее (готовый серверный текст) → возвращаем без изменений.
 */
export function translateFieldError(
  t: Translate,
  message: string | undefined,
): string | undefined {
  if (!message) return message
  if (message.charCodeAt(0) === 123 /* '{' */) {
    try {
      const decoded = JSON.parse(message) as EncodedError
      if (decoded && typeof decoded.key === 'string') {
        return t(decoded.key, decoded.params)
      }
    } catch {
      // не валидный JSON — обрабатываем как обычный текст ниже
    }
  }
  // i18n-ключ: `namespace:dot.path` — ns латиницей (вкл. camelCase, напр. operatorForm),
  // затем ':' и dot-path без пробелов. Якорим `$` + запрет пробелов/слешей → проза
  // («warning: …») и URL («https://…») НЕ матчатся (возвращаются как готовый текст).
  if (/^[a-z][a-zA-Z0-9]*:[\w.]+$/.test(message)) return t(message)
  return message
}
