import { AttendeeForm } from 'frontend'

// В add-режиме форма грузит RBAC-scoped список категорий (GET /api/v1/requests/) для
// селекта «Категория». Бэкенда в превью нет — подменяем window.fetch, чтобы селект был
// заполнен реальными мероприятиями. В edit-режиме (ReadOnly) запрос отключён (enabled:false),
// поэтому стаб на него не влияет.
const originalFetch = window.fetch.bind(window)
window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  const url =
    typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
  if (url.includes('/requests')) {
    return Promise.resolve(
      new Response(
        JSON.stringify({
          count: 3,
          next: null,
          previous: null,
          results: [
            { id: 12, name: 'Пресса', event_id: 1, event_name: 'Форум «Цифровой Казахстан 2026»' },
            { id: 15, name: 'Делегаты', event_id: 1, event_name: 'Форум «Цифровой Казахстан 2026»' },
            { id: 21, name: 'VIP-гости', event_id: 2, event_name: 'Астанинский экономический саммит' },
          ],
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    )
  }
  return originalFetch(input, init)
}) as typeof window.fetch

// Резидент → показано поле ИИН; нерезидент 643 — тоже опция. countryId по умолчанию =
// KZ_COUNTRY_ID ('1000000105'), поэтому в пустой форме блок ИИН уже виден.
export function Empty() {
  return <AttendeeForm />
}

const PHOTO_PLACEHOLDER =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400"><rect width="300" height="400" fill="#e3e5e8"/><circle cx="150" cy="150" r="60" fill="#7c828a"/><path d="M60 400c0-70 40-110 90-110s90 40 90 110" fill="#7c828a"/></svg>',
  )

const DOC_PLACEHOLDER =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400"><rect width="300" height="400" fill="#eef0f2"/><rect x="24" y="28" width="120" height="150" rx="6" fill="#c7ccd1"/><rect x="160" y="40" width="116" height="14" rx="7" fill="#c7ccd1"/><rect x="160" y="70" width="90" height="12" rx="6" fill="#c7ccd1"/><rect x="24" y="210" width="252" height="12" rx="6" fill="#c7ccd1"/><rect x="24" y="238" width="252" height="12" rx="6" fill="#c7ccd1"/><rect x="24" y="266" width="180" height="12" rx="6" fill="#c7ccd1"/></svg>',
  )

// Edit + readOnly (статус ready/exported): read-only баннер, все поля заблокированы
// (fieldset disabled), фото/документ показаны из initial*Url. Категория в edit disabled
// и через fallback-опцию отображает уже назначенную заявку (#15).
export function ReadOnly() {
  return (
    <AttendeeForm
      attendeeId={4821}
      readOnly
      initialValues={{
        surname: 'Нұрланова',
        firstname: 'Айгерім',
        patronymic: 'Қайратқызы',
        birthDate: '1990-03-22',
        countryId: '1000000105',
        iin: '900322400818',
        request: '15',
      }}
      initialPhotoUrl={PHOTO_PLACEHOLDER}
      initialDocScanUrl={DOC_PLACEHOLDER}
    />
  )
}
