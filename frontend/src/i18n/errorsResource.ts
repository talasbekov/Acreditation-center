// Story fe-1.3 (AC-4): pivot errors.json (code-major) into the i18next "errors"
// namespace (locale-major). Single source: src/errors/errors.json, which is
// contract-tested against the DRF registry (errorContract.test.ts). We do NOT create
// locales/*/errors.json: a second copy would silently bypass the contract test and the
// catalogs would drift from the DRF registry.
import errorsByCode from '@/errors/errors.json'

// fe-1.2 (code-review P1): en/kz значения в errors.json — пока `[ASSUMPTION] <ru>`-
// плейсхолдеры (fe-1.1). Не переносим их в namespace, иначе dev-маркер `[ASSUMPTION]`
// утечёт в UI на каждой серверной ошибке в en/kz. Отбрасываем → i18next фолбэчит на
// чистый ru (консистентно с пустыми kz-каталогами common/status/nav). Реальные kz/en
// переводы ошибок придут общим треком локализации (fe-1.4 / kz legal gate).
const ASSUMPTION_PREFIX = '[ASSUMPTION]'

export function buildErrorsResource(
  langs: readonly string[],
): Record<string, Record<string, string>> {
  const source = errorsByCode as Record<string, unknown>
  const out: Record<string, Record<string, string>> = {}
  for (const lng of langs) out[lng] = {}
  for (const code of Object.keys(source)) {
    const byLang = source[code]
    // Guard: errors.json контракт-тестируется, но если значение кода вдруг не-объект
    // (null/строка), пропускаем код, а не падаем на импорте модуля (краш всего SPA).
    if (byLang === null || typeof byLang !== 'object') continue
    for (const lng of langs) {
      const value = (byLang as Record<string, unknown>)[lng]
      if (typeof value === 'string' && !value.startsWith(ASSUMPTION_PREFIX)) {
        out[lng][code] = value
      }
    }
  }
  return out
}
