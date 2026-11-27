import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { TONE_CLASSES } from '@/components/StatusBadge'

// AC-2 (fe-2.4): контраст текста на tint проверяется ПРОГРАММНО (≥4.5:1, WCAG AA), не на глаз.
// Живёт в scripts/ (как lint-tokens.test.ts) — использует node:fs, вне app-typecheck,
// но в vite.config test.include. Drift-proof: hex из index.css (источник токенов fe-2.1),
// пары fg/bg — из самих классов компонента TONE_CLASSES (суффикс утилиты == имя переменной).
// cwd vitest = frontend/.
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')

function tokenHex(name: string): string {
  // Первое совпадение = :root (light) — идёт в файле до .dark.
  const m = css.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`))
  if (!m) throw new Error(`token --${name} не найден в index.css`)
  return m[1]
}

function srgbToLinear(channel: number): number {
  const s = channel / 255
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b)
}

function contrastRatio(fgHex: string, bgHex: string): number {
  const l1 = luminance(fgHex)
  const l2 = luminance(bgHex)
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1]
  return (hi + 0.05) / (lo + 0.05)
}

// Достаём токен из утилиты (`text-…`/`bg-…`) → имя CSS-переменной. Явный guard:
// при будущем тоне без нужной утилиты — чистая ошибка, а не TypeError от non-null `!`.
function utilToken(cls: string, prefix: 'text' | 'bg'): string {
  const m = cls.match(new RegExp(`${prefix}-([\\w-]+)`))
  if (!m) throw new Error(`класс "${cls}" не содержит ${prefix}-* утилиту`)
  return m[1]
}

const tonePairs = Object.entries(TONE_CLASSES).map(([tone, { badge, dot }]) => ({
  tone,
  fg: utilToken(badge, 'text'),
  bg: utilToken(badge, 'bg'),
  dotToken: utilToken(dot, 'bg'),
}))

describe('StatusBadge contrast (fe-2.4 AC-2)', () => {
  it.each(tonePairs)('тон $tone: текст на tint ≥ 4.5:1 (WCAG AA)', ({ fg, bg }) => {
    expect(contrastRatio(tokenHex(fg), tokenHex(bg))).toBeGreaterThanOrEqual(4.5)
  })

  // Точка-dot — графический объект (colorblind-избыточность): WCAG 1.4.11 ≥3:1 на tint-фоне.
  it.each(tonePairs)('тон $tone: точка-dot на tint ≥ 3:1 (WCAG 1.4.11)', ({ dotToken, bg }) => {
    expect(contrastRatio(tokenHex(dotToken), tokenHex(bg))).toBeGreaterThanOrEqual(3)
  })
})
