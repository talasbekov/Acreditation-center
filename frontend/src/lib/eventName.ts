/**
 * Story fe-1.5 — выбор локализованного имени события по активной локали.
 *
 * Имена событий — ДАННЫЕ (не UI-строки): backend отдаёт все три (`sub_event_names`/EventSerializer),
 * React выбирает здесь. Fallback-цепочка (AC3): активный язык → `ru` → `fallbackTitle` → '—'.
 * Листовые события часто имеют только `ru` (kz/en пусты/null) → падаем на `ru`, не пустой заголовок.
 *
 * ⚠ `lang` — app-key из `i18n.language` (`'ru'|'kz'|'en'`), НЕ `<html lang>` (`'kk'`).
 * `names` может быть `null`/`undefined` (нет под-события).
 */
export interface TrilingualName {
  ru: string | null
  kz: string | null
  en: string | null
}

export function pickLocalizedName(
  names: TrilingualName | null | undefined,
  lang: string,
  fallbackTitle?: string | null,
): string {
  const byLang = lang === 'kz' ? names?.kz : lang === 'en' ? names?.en : names?.ru
  // `||` глотает и пустую строку, и null → следующий фолбэк.
  return byLang || names?.ru || fallbackTitle || '—'
}
