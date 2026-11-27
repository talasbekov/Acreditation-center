import type { TFunction, i18n as I18n } from 'i18next'
import type { ProblemDetail } from '@/api/client'

// Story fe-1.2: серверный машинный код ошибки -> локализованный текст.
// known: t('errors:'+type, params) с интерполяцией. unknown/missing: лог type + общий
// t('errors:unknown'). Сырой code/type оператору НИКОГДА не показывается как текст.
// `errors` namespace и `errors:unknown` приходят из единого errors.json (fe-1.1/fe-1.3).
export function mapApiError(
  problem: ProblemDetail | undefined,
  t: TFunction,
  i18n: I18n,
): string {
  const type = problem?.type
  if (type && i18n.exists(`errors:${type}`)) {
    const text = t(`errors:${type}`, { ...(problem?.params ?? {}) })
    // exists может быть true при пустом значении каталога → t() вернёт сам ключ.
    // Тогда не показываем «errors:<code>» оператору, а падаем в unknown ниже.
    if (text && text !== `errors:${type}`) return text
  }
  if (type) {
    // Лог в консоль/телеметрию — НЕ в UI (dev-диагностика, поэтому английский).
    console.warn('[error-mapper] unknown error code:', type)
  }
  return t('errors:unknown')
}
