import { test, expect } from '@playwright/test'
import { mockApi, ATTENDEE_DETAIL } from './_fixtures'

test.describe('Редактирование участника (Story 5.5 + P2-2/6/7)', () => {
  test('предзаполняет форму, request read-only, превью фото/документа', async ({
    page,
  }) => {
    await mockApi(page)
    await page.goto('/attendees/1')

    // Предзаполнение (AC-5).
    await expect(page.getByLabel('Фамилия')).toHaveValue('Иванов')
    await expect(page.locator('#iin')).toHaveValue('900515312349')

    // P2-6: мероприятие read-only — нельзя «переселить» участника.
    await expect(page.locator('#request')).not.toBeEditable()

    // P2-7: показаны уже загруженные фото и документ.
    await expect(page.getByAltText(/Текущее: ФОТО УЧАСТНИКА/i)).toBeVisible()
    await expect(page.getByAltText(/Текущее: ФОТО ДОКУМЕНТА/i)).toBeVisible()
  })

  test('read-only баннер при статусе ready', async ({ page }) => {
    await mockApi(page, { ...ATTENDEE_DETAIL, status: 'ready' })
    await page.goto('/attendees/1')
    await expect(page.getByText('Редактирование заблокировано')).toBeVisible()
    await expect(page.getByRole('button', { name: /Сохранить/ })).toHaveCount(0)
  })

  // P2-2: 404 detail → различимое сообщение «не найден».
  test('404 detail → «участник не найден»', async ({ page }) => {
    await page.route('**/api/v1/csrf/', (r) =>
      r.fulfill({ status: 200, json: { detail: 'ok' } }),
    )
    // Конкретный detail → 404 (регистрируем ДО catch-all, чтобы fallback его достиг).
    await page.route('**/api/v1/attendees/1/', (r) =>
      r.fulfill({ status: 404, json: { detail: 'Not found' } }),
    )
    await page.route('**/api/v1/attendees/**', (r) => {
      if (r.request().url().includes('/attendees/1/')) return r.fallback()
      return r.fulfill({
        status: 200,
        json: { count: 0, next: null, previous: null, results: [] },
      })
    })
    await page.goto('/attendees/1')
    await expect(page.getByText(/не найден/i)).toBeVisible()
  })
})
