import { useTranslation } from 'react-i18next'

/**
 * Story fe-1.3 (AC-2) — переключатель языка ru/kz/en.
 *
 * Временно живёт в минимальной шапке App. Полноценный app-shell + role-filtered nav —
 * fe-2-2; финальный визуал и место свитчера в шапке — fe-2-3.
 */
const LANGS = [
  { code: 'ru', label: 'RU' },
  { code: 'kz', label: 'KZ' },
  { code: 'en', label: 'EN' },
] as const

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation()
  // active = ВЫБРАННЫЙ язык (i18n.language), а не resolvedLanguage: последний проседает
  // на фолбэк (ru), когда у локали пустые каталоги (kz-каркас) — тогда KZ никогда не
  // подсветился бы активным. load:'languageOnly' уже снимает регион.
  const active = i18n.language

  return (
    <div role="group" aria-label={t('nav:language')} className="flex gap-1">
      {LANGS.map(({ code, label }) => {
        const isActive = active === code
        return (
          <button
            key={code}
            type="button"
            aria-current={isActive ? 'true' : undefined}
            disabled={isActive}
            onClick={() => void i18n.changeLanguage(code)}
            className={
              'rounded px-2 py-1 text-sm font-medium ' +
              (isActive
                ? 'bg-neutral-200 text-neutral-900'
                : 'text-neutral-600 hover:bg-neutral-100')
            }
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
