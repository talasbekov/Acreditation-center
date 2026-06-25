import { test, expect } from '@playwright/test'
import { mockApi } from './_fixtures'

test.describe('Список участников (Story 5.1/5.5)', () => {
  test('загружается и показывает строки', async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
    await expect(
      page.getByRole('heading', { name: 'Участники' }),
    ).toBeVisible()
    await expect(page.getByText('Иванов Иван Иванович')).toBeVisible()
    await expect(page.getByText('Петров Пётр')).toBeVisible()
    // ИИН в списке — только маскированный (PII-минимизация, 5.5).
    await expect(page.getByText('********1234')).toBeVisible()
  })

  test('без сессии (403 session-check) → редирект на Django-логин с next', async ({
    page,
  }) => {
    await page.route('**/api/v1/csrf/', (route) =>
      route.fulfill({ status: 200, json: { detail: 'ok' } }),
    )
    // FE-3: session-check идёт через rbac-пробник → именно он должен вернуть 403.
    await page.route('**/api/v1/rbac-check/', (route) =>
      route.fulfill({ status: 403, json: { detail: 'Forbidden' } }),
    )
    await page.route('**/api/v1/attendees/**', (route) =>
      route.fulfill({ status: 403, json: { detail: 'Forbidden' } }),
    )
    // /user_login/ обслуживает Django; в dev отдаём заглушку, чтобы проверить redirect+next.
    await page.route('**/user_login/**', (route) =>
      route.fulfill({ status: 200, contentType: 'text/html', body: '<h1>LOGIN</h1>' }),
    )
    await page.goto('/')
    await page.waitForURL(/\/user_login\/\?next=/)
    expect(page.url()).toContain('next=')
  })
})
