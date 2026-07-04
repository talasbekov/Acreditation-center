import { AppShell } from 'frontend'

// AppShell обращается к бэкенду дважды: GET /api/v1/rbac-check/ (роль → role-filtered
// nav через useRole) и getAttendees({returned:true}) (счётчик возвратов для бейджа на
// пункте «Возвраты»). В превью бэкенда нет — подменяем window.fetch на уровне модуля:
// роль superuser раскрывает полную навигацию (очередь/события/экспорт/журнал/…), а
// count:3 показывает красный бейдж-счётчик. Остальные запросы уходят в оригинальный fetch.
const originalFetch = window.fetch.bind(window)
window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  const url =
    typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
  const json = (body: unknown) =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
  if (url.includes('rbac-check')) return json({ role: 'superuser' })
  if (url.includes('/attendees'))
    return json({ count: 3, next: null, previous: null, results: [] })
  return originalFetch(input, init)
}) as typeof window.fetch

export function OperatorShell() {
  return <AppShell />
}
