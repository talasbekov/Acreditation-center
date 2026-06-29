import axe, { type AxeResults, type Result, type ImpactValue } from 'axe-core'

/**
 * Story fe-2.5 — именованный axe-конфиг-артефакт (AC-1). Единый источник правил для всех
 * a11y-тестов (не копипаст). Теги — WCAG 2.0/2.1 уровня A/AA.
 *
 * ⚠️ ОБЛАСТЬ ПОКРЫТИЯ (честно): jsdom-axe — это **структурный floor** (роли/имена/`aria-*`/
 * `<html lang>`/дубли id/label/image-alt — реально валятся при регрессии, проверено probe).
 * Layout-зависимые правила (`color-contrast`, `target-size`, `reflow`) в jsdom невычислимы →
 * уходят в `results.incomplete` (НЕ `violations`), т.е. этим гейтом НЕ проверяются. Их закрывают:
 * (1) Playwright real-browser axe (e2e/a11y.spec.ts, вкл. contrast); (2) fe-2.4
 * `scripts/status-badge-contrast.test.ts` (программный WCAG-контраст) + `lint:tokens`.
 * focus-order/keyboard-trap axe не видит вовсе → отдельный keyboard-pass (AC-2).
 * Вывод: «0 critical/serious» здесь = структурный floor, НЕ полная верификация WCAG-AA.
 */
export const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

export function runAxe(node: Element | Document = document): Promise<AxeResults> {
  return axe.run(node, {
    runOnly: { type: 'tag', values: WCAG_TAGS },
    // jsdom не умеет canvas/layout → color-contrast невычислим (шумит «getContext not implemented»).
    // Контраст гейтится отдельно (StatusBadge contrast-тест + lint:tokens) и в Playwright (real-browser).
    rules: { 'color-contrast': { enabled: false } },
  })
}

/** Нарушения уровня critical/serious — порог floor-гейта (AC-1). */
export function criticalOrSerious(results: AxeResults): Result[] {
  const blocking: ImpactValue[] = ['critical', 'serious']
  return results.violations.filter((v) => v.impact != null && blocking.includes(v.impact))
}
