import { describe, it, expect } from 'vitest'

import ruCommon from '@/locales/ru/common.json'
import ruValidation from '@/locales/ru/validation.json'
import ruStatus from '@/locales/ru/status.json'
import ruNav from '@/locales/ru/nav.json'
import ruOperatorForm from '@/locales/ru/operatorForm.json'
import kzCommon from '@/locales/kz/common.json'
import kzValidation from '@/locales/kz/validation.json'
import kzStatus from '@/locales/kz/status.json'
import kzNav from '@/locales/kz/nav.json'
import kzOperatorForm from '@/locales/kz/operatorForm.json'
import enCommon from '@/locales/en/common.json'
import enValidation from '@/locales/en/validation.json'
import enStatus from '@/locales/en/status.json'
import enNav from '@/locales/en/nav.json'
import enOperatorForm from '@/locales/en/operatorForm.json'

type Catalog = Record<string, unknown>

function flattenKeys(obj: Catalog, prefix = ''): string[] {
  const out: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
      out.push(...flattenKeys(v as Catalog, path))
    } else {
      out.push(path)
    }
  }
  return out
}

// ru — источник правды; kz И en должны покрывать КАЖДЫЙ ключ (иначе fallback-сюрприз на ru
// для соответствующей локали). Кортеж: [ns, ru, kz, en].
const NAMESPACES: Array<[string, Catalog, Catalog, Catalog]> = [
  ['common', ruCommon, kzCommon, enCommon],
  ['validation', ruValidation, kzValidation, enValidation],
  ['status', ruStatus, kzStatus, enStatus],
  ['nav', ruNav, kzNav, enNav],
  ['operatorForm', ruOperatorForm, kzOperatorForm, enOperatorForm],
]

describe('catalog completeness (Story fe-1.4 AC-2/Task7) — kz и en покрывают ru', () => {
  it.each(NAMESPACES)('%s: каждый ru-ключ имеет kz-аналог (нет пропусков)', (_ns, ru, kz) => {
    const kzKeys = new Set(flattenKeys(kz))
    const missing = flattenKeys(ru).filter((k) => !kzKeys.has(k))
    expect(missing).toEqual([])
  })

  it.each(NAMESPACES)('%s: каждый ru-ключ имеет en-аналог (нет пропусков)', (_ns, ru, _kz, en) => {
    const enKeys = new Set(flattenKeys(en))
    const missing = flattenKeys(ru).filter((k) => !enKeys.has(k))
    expect(missing).toEqual([])
  })

  it.each(NAMESPACES)('%s: kz без лишних ключей (нет дрейфа от ru)', (_ns, ru, kz) => {
    const ruKeys = new Set(flattenKeys(ru))
    const extra = flattenKeys(kz).filter((k) => !ruKeys.has(k))
    expect(extra).toEqual([])
  })
})

describe('anti-tofu / непустые значения (Story fe-1.4 AC-3) — kz и en', () => {
  function assertNoTofu(cat: Catalog) {
    const json = JSON.stringify(cat)
    expect(json.includes('□')).toBe(false)
    expect(json.includes('�')).toBe(false)
  }
  function assertNoEmpty(cat: Catalog) {
    const empties = flattenKeys(cat).filter((path) => {
      const value = path.split('.').reduce<unknown>((acc, seg) => (acc as Catalog)?.[seg], cat)
      return typeof value === 'string' && value.trim() === ''
    })
    expect(empties).toEqual([])
  }

  it.each(NAMESPACES)('%s: kz без □/U+FFFD и непустые', (_ns, _ru, kz) => {
    assertNoTofu(kz)
    assertNoEmpty(kz)
  })

  it.each(NAMESPACES)('%s: en без □/U+FFFD и непустые', (_ns, _ru, _kz, en) => {
    assertNoTofu(en)
    assertNoEmpty(en)
  })
})
