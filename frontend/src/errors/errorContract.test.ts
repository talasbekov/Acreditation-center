import { describe, expect, it } from 'vitest'

import codesJson from './errors.codes.json'
import dictJson from './errors.json'
import samplesJson from './__fixtures__/drf-error-samples.json'
import { drfErrorSchema } from './schema'

/**
 * Story fe-1.1 (AC-3) — consumer-driven contract-тест zod↔DRF.
 *
 * Источник DRF-кодов — `errors.codes.json` (генерирует `manage.py export_error_codes`
 * из единого реестра `eventproject/errors/registry.py`; анти-дрейф пинит backend-тест
 * `test_error_contract.py`). Фронтовый словарь — `errors.json`. Коды НЕ хардкодятся в
 * тесте (иначе он тавтологичен) — читаются из закоммиченных артефактов.
 */
const drfCodes = Object.keys(codesJson)
const zodKeys = Object.keys(dictJson)
const samples = samplesJson as unknown[]

/**
 * ЕДИНСТВЕННЫЙ асертер равенства множеств — его же зовёт negative-тест (а не копию
 * логики), иначе negative доказывал бы работу копии, а не продакшн-проверки.
 */
function assertSetEquality(drf: string[], zod: string[]): void {
  const zodSet = new Set(zod)
  const drfSet = new Set(drf)
  const missingInZod = drf.filter((code) => !zodSet.has(code))
  const missingInDrf = zod.filter((code) => !drfSet.has(code))
  if (missingInZod.length > 0 || missingInDrf.length > 0) {
    throw new Error(
      `set mismatch — коды реестра без ключа в errors.json: [${missingInZod}]; ` +
        `ключи errors.json без кода в реестре: [${missingInDrf}]`,
    )
  }
}

describe('Контракт ошибок zod↔DRF (story fe-1.1, AC-3)', () => {
  it('равенство множеств: set(DRF_codes) === set(zod_keys) в ОБЕ стороны', () => {
    expect(() => assertSetEquality(drfCodes, zodKeys)).not.toThrow()
  })

  it('zod-схема валидирует РЕАЛЬНЫЕ DRF-ответы (round-trip) и type имеет UI-ключ', () => {
    expect(samples.length).toBeGreaterThan(0)
    for (const sample of samples) {
      const parsed = drfErrorSchema.parse(sample) // бросит при несовпадении shape
      expect(zodKeys, `type=${parsed.type} без ключа в errors.json`).toContain(parsed.type)
    }
  })

  it('negative (тест-на-тест): осиротевший код → ТОТ ЖЕ асертер ПАДАЕТ', () => {
    // Не подмножество: лишний код на DRF-стороне ломает равенство.
    expect(() => assertSetEquality([...drfCodes, '__orphan_code_xyz__'], zodKeys)).toThrow(
      /__orphan_code_xyz__/,
    )
    // И обратное направление: лишний ключ на zod-стороне тоже ломает.
    expect(() => assertSetEquality(drfCodes, [...zodKeys, '__orphan_key_abc__'])).toThrow(
      /__orphan_key_abc__/,
    )
  })
})
