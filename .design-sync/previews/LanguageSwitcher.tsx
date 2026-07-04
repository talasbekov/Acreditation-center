import { LanguageSwitcher } from 'frontend'

// Переключатель языка ru/kz/en из шапки кабинета оператора. Активный язык (RU по
// умолчанию) подсвечен токеном primary-tint и задизейблен; неактивные — text-muted
// с hover:bg-surface-muted.
export function Default() {
  return (
    <div style={{ padding: 24 }}>
      <LanguageSwitcher />
    </div>
  )
}
