import { test, expect } from '@playwright/test'
import { mockApi } from './_fixtures'

test.describe('Добавление участника — форма (Story 5.2)', () => {
  test('residency-toggle: не-Казахстан скрывает поле ИИН', async ({ page }) => {
    await mockApi(page)
    await page.goto('/add')

    // По умолчанию резидент РК → поле ИИН видно.
    await expect(page.getByLabel('ИИН')).toBeVisible()

    // Сменили страну на нерезидента → ИИН исчезает (AC-3).
    await page.getByLabel('Страна').selectOption('643')
    await expect(page.getByLabel('ИИН')).toHaveCount(0)
  })
})
