import { StatusBadge } from 'frontend'

// Все статусы state-machine заявки: цвет НЕ единственный носитель смысла (dot + текст).
// Подписи приходят из i18n namespace `status` (ru).
export function AllStatuses() {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
      <StatusBadge status="draft" />
      <StatusBadge status="submitted" />
      <StatusBadge status="in_review" />
      <StatusBadge status="ready" />
      <StatusBadge status="exported" />
    </div>
  )
}

// Неизвестный код статуса → нейтральный тон (defensive), пустой → «—».
export function EdgeCases() {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
      <StatusBadge status="archived" />
      <StatusBadge status="" />
    </div>
  )
}
