import { test, expect } from '@playwright/test'
import { mockApi } from './_fixtures'

test.describe('Добавление участника — форма (Story 5.2)', () => {
  test('residency-toggle: не-Казахстан скрывает поле ИИН', async ({ page }) => {
    await mockApi(page)
    await page.goto('/add')

    // По умолчанию резидент РК → поле ИИН видно.
    await expect(page.getByLabel('ИИН')).toBeVisible()

    // Сменили страну на нерезидента → ИИН исчезает (AC-3).
    await page.getByLabel('Гражданство').selectOption('643')
    await expect(page.getByLabel('ИИН')).toHaveCount(0)
  })
})

test('общее рабочее место: удаление старого черновика и новая сессия', async ({ page, context }) => {
  await mockApi(page)
  await page.addInitScript(() => {
    localStorage.setItem('attendee_draft_v1', JSON.stringify({ surname: 'Старый' }))
    localStorage.setItem('language', 'ru')
  })
  await page.goto('/')
  await expect(page.getByText('Иванов', { exact: false }).first()).toBeVisible()
  expect(await page.evaluate(() => localStorage.getItem('attendee_draft_v1'))).toBeNull()
  expect(await page.evaluate(() => localStorage.getItem('language'))).toBe('ru')

  await page.goto('/add')
  await expect(page.getByLabel('Фамилия')).toHaveValue('')
  await page.getByLabel('Фамилия').fill('Первый оператор')
  await page.getByLabel('ИИН').fill('123456789012')
  await page.close()

  const next = await context.newPage()
  await mockApi(next)
  await next.goto('/add')
  await expect(next.getByLabel('Фамилия')).toHaveValue('')
  await expect(next.getByLabel('ИИН')).toHaveValue('')
  await expect(next.getByText(/Восстановить/)).toHaveCount(0)
})

test('возврат к форме из кэша истории проверяет сессию заново', async ({ page }) => {
  await mockApi(page)
  await page.goto('/add')
  await page.getByLabel('Фамилия').fill('Первый оператор')
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true })))
  await expect(page.getByLabel('Фамилия')).toHaveCount(0)
  const checked = page.waitForRequest('**/api/v1/rbac-check/')
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })))
  await checked
  await expect(page.getByLabel('Фамилия')).toHaveValue('')
})
