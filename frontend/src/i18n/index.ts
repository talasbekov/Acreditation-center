/**
 * Story fe-1.3 — bootstrap react-i18next (плумбинг).
 *
 * Ресурсы БАНДЛЯТСЯ (импорт JSON), без сетевого backend → init синхронный, нет flash и
 * гонки с async-проверкой сессии в RequireAuth. Поэтому `react.useSuspense: false`
 * (Suspense-границы в приложении нет). Namespaces: common/validation/errors/status/nav.
 * `errors` — pivot из единого `src/errors/errors.json` (см. errorsResource.ts, AC-4).
 *
 * Ключи локали приложения: ru/kz/en. ISO-маппинг для `<html lang>` (kz→kk) — htmlLang.ts.
 */
import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import { buildErrorsResource } from '@/i18n/errorsResource'
import { syncHtmlLang } from '@/i18n/htmlLang'

import ruCommon from '@/locales/ru/common.json'
import ruValidation from '@/locales/ru/validation.json'
import ruStatus from '@/locales/ru/status.json'
import ruNav from '@/locales/ru/nav.json'
import kzCommon from '@/locales/kz/common.json'
import kzValidation from '@/locales/kz/validation.json'
import kzStatus from '@/locales/kz/status.json'
import kzNav from '@/locales/kz/nav.json'
import enCommon from '@/locales/en/common.json'
import enValidation from '@/locales/en/validation.json'
import enStatus from '@/locales/en/status.json'
import enNav from '@/locales/en/nav.json'

export const SUPPORTED_LNGS = ['ru', 'kz', 'en'] as const
export const FALLBACK_LNG = 'ru'
export const LANG_STORAGE_KEY = 'accreditation.lng'

// `errors` namespace выводим pivot'ом из errors.json (единый contract-тестируемый источник).
const errorsResource = buildErrorsResource(SUPPORTED_LNGS)

const resources = {
  ru: { common: ruCommon, validation: ruValidation, status: ruStatus, nav: ruNav, errors: errorsResource.ru },
  kz: { common: kzCommon, validation: kzValidation, status: kzStatus, nav: kzNav, errors: errorsResource.kz },
  en: { common: enCommon, validation: enValidation, status: enStatus, nav: enNav, errors: errorsResource.en },
}

i18n.use(LanguageDetector).use(initReactI18next)

if (!i18n.isInitialized) {
  void i18n.init({
    resources,
    supportedLngs: [...SUPPORTED_LNGS],
    fallbackLng: FALLBACK_LNG,
    load: 'languageOnly', // 'ru-RU' → 'ru'; 'en-US' → 'en'
    ns: ['common', 'validation', 'errors', 'status', 'nav'],
    defaultNS: 'common',
    interpolation: { escapeValue: false }, // React уже экранирует — иначе двойное экранирование
    returnEmptyString: false, // пустое значение в каталоге → фолбэк на ru, а не пустой рендер
    react: { useSuspense: false },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: LANG_STORAGE_KEY,
      // Браузер казахского отдаёт 'kk*' (ISO), а ключ локали приложения — 'kz'.
      convertDetectedLanguage: (lng: string) =>
        lng.toLowerCase().startsWith('kk') ? 'kz' : lng,
    },
  })

  // Внутри init-guard, чтобы под Vite HMR не накапливались дубли listener'ов.
  // `<html lang>` синхронизируется при каждой смене языка И один раз на старте.
  // Берём i18n.language (ВЫБРАННЫЙ язык: kz→kk), а не resolvedLanguage (тот проседает
  // на ru при пустых kz-каталогах → потеряли бы `lang="kk"` при сохранённом выборе kz).
  i18n.on('languageChanged', syncHtmlLang)
  syncHtmlLang(i18n.language)
}

export default i18n
