/**
 * Story fe-1.3 (AC-3) — синхронизация `<html lang>` с активной локалью.
 *
 * ВАЖНО: ключ локали приложения для казахского — `kz` (как `name_kz`, `locales/kz/`),
 * но валидный ISO 639-1 для казахского — `kk`. `<html lang="kz">` невалиден, поэтому
 * локаль приложения маппится в ISO-код документа. ru→ru, kz→kk, en→en.
 */
export const HTML_LANG: Record<string, string> = {
  ru: 'ru',
  kz: 'kk',
  en: 'en',
}

/** Ставит `document.documentElement.lang` по активной локали (с фолбэком на ru). */
export function syncHtmlLang(lng: string | undefined): void {
  if (typeof document === 'undefined') return
  const base = (lng ?? 'ru').split('-')[0]
  document.documentElement.lang = HTML_LANG[base] ?? 'ru'
}
