import type { Page } from '@playwright/test'

export const ATTENDEE_LIST = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 1,
      surname: 'Иванов',
      firstname: 'Иван',
      patronymic: 'Иванович',
      status: 'draft',
      category: null,
      dateAdd: '2026-06-24T10:00:00Z',
      iin_masked: '********1234',
    },
    {
      id: 2,
      surname: 'Петров',
      firstname: 'Пётр',
      patronymic: null,
      status: 'ready',
      category: null,
      dateAdd: '2026-06-24T11:00:00Z',
      iin_masked: '********5678',
    },
  ],
}

export const ATTENDEE_DETAIL = {
  id: 1,
  surname: 'Иванов',
  firstname: 'Иван',
  patronymic: 'Иванович',
  birthDate: '1990-05-15',
  countryId: '1000000105',
  iin: '900515312349',
  request: 7,
  status: 'draft',
  photo: '/media/event_1/1_photo.jpg',
  docScan: '/media/event_1/1_doc.jpg',
}

/** Мокаем DRF: csrf-bootstrap, session-check/list, detail, media-картинки. */
export async function mockApi(page: Page, detail = ATTENDEE_DETAIL) {
  await page.route('**/api/v1/csrf/', (route) =>
    route.fulfill({ status: 200, json: { detail: 'ok' } }),
  )
  // FE-3: session-check теперь через rbac-пробник (не /attendees/?page_size=1).
  await page.route('**/api/v1/rbac-check/', (route) =>
    route.fulfill({ status: 200, json: { role: 'operator' } }),
  )
  // FE-1: форма добавления грузит RBAC-scoped список категорий для <select>.
  await page.route('**/api/v1/requests/**', (route) =>
    route.fulfill({
      status: 200,
      json: {
        count: 1,
        next: null,
        previous: null,
        results: [
          { id: 7, name: 'Категория А', event_id: 1, event_name: 'Событие 1' },
        ],
      },
    }),
  )
  await page.route('**/api/v1/attendees/1/', (route) =>
    route.fulfill({ status: 200, json: detail }),
  )
  // Список + session-check (?page_size=1) — общий префикс.
  await page.route('**/api/v1/attendees/**', (route) => {
    if (route.request().url().includes('/attendees/1/')) return route.fallback()
    return route.fulfill({ status: 200, json: ATTENDEE_LIST })
  })
  // Медиа-превью (P2-7): отдаём 1×1 PNG, чтобы <img> не висел 404.
  await page.route('**/media/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
        'base64',
      ),
    }),
  )
}
