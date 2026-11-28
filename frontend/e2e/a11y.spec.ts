import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { mockApi } from './_fixtures'

// Story fe-2.5 — real-browser слой a11y (то, что jsdom не может): axe С color-contrast +
// faithful keyboard focus-move. `mockApi` мокает rbac-check→operator → shell рендерится.
// focus-trap оверлея/модалки — отложено (нет оверлея в WAVE-0; см. deferred-work, к E3a).
const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

function criticalOrSerious(violations: { impact?: string | null; id: string }[]) {
  return violations.filter((v) => v.impact === 'critical' || v.impact === 'serious').map((v) => v.id)
}

test.describe('a11y axe + keyboard-pass (fe-2.5)', () => {
  test('axe: 0 critical/serious на каркасе (/) — real-browser, вкл. color-contrast', async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
    await page.getByText('Участники').first().waitFor()
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze()
    expect(criticalOrSerious(results.violations)).toEqual([])
  })

  test('axe: 0 critical/serious на форме (/add) — выборочно', async ({ page }) => {
    await mockApi(page)
    await page.goto('/add')
    await page.getByRole('button', { name: 'Сохранить' }).waitFor()
    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze()
    expect(criticalOrSerious(results.violations)).toEqual([])
  })

  test('keyboard-pass: Tab → skip-link (виден) → Enter → фокус реально в <main>', async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
    await page.getByText('Участники').first().waitFor()
    await page.keyboard.press('Tab')
    const skip = page.locator('a[href="#main-content"]')
    await expect(skip).toBeFocused() // первый фокусируемый
    await expect(skip).toBeVisible() // раскрылся из sr-only при фокусе (focus:not-sr-only)
    await page.keyboard.press('Enter')
    // faithful focus-move: фокус ушёл в <main tabIndex=-1> (jsdom это не моделирует).
    // web-first assertion (авто-ретрай) — не одноразовый снимок activeElement.
    await expect(page.locator('#main-content')).toBeFocused()
  })

  test('фокус-ринг виден на интерактивном элементе при фокусе (computed)', async ({ page }) => {
    await mockApi(page)
    await page.goto('/')
    await page.getByText('Участники').first().waitFor()
    const firstNav = page.getByRole('navigation').getByRole('link').first()
    await firstNav.focus()
    await expect(firstNav).toBeFocused()
    // реально проверяем индикатор фокуса: ring-2 → box-shadow, либо outline (не оба 'none')
    const indicator = await firstNav.evaluate((el) => {
      const s = getComputedStyle(el)
      return `${s.boxShadow}|${s.outlineStyle}`
    })
    expect(indicator).not.toBe('none|none')
  })
})
