import { describe, it, expect } from 'vitest'
import { computeCatalogHash, evaluateReview } from './check-kz-review.mjs'

// Story fe-1.4 (AC-4): гейт kz-review «не протухает молча», но и не блокирует
// первичный мердж (date:null → warn). Тестируем чистое решение + детерминизм хэша.
describe('check-kz-review (Story fe-1.4)', () => {
  describe('evaluateReview', () => {
    it('date:null → warn, exit 0 (dev-гейт не блокируется)', () => {
      const r = evaluateReview('abc', { date: null, catalog_hash: 'abc' })
      expect(r.status).toBe('warn')
      expect(r.exitCode).toBe(0)
    })

    it('нет record → warn, exit 0', () => {
      const r = evaluateReview('abc', null)
      expect(r.status).toBe('warn')
      expect(r.exitCode).toBe(0)
    })

    it('отревьюено + hash совпадает → ok, exit 0', () => {
      const r = evaluateReview('abc', { date: '2026-07-01', catalog_hash: 'abc' })
      expect(r.status).toBe('ok')
      expect(r.exitCode).toBe(0)
    })

    it('отревьюено + hash РАЗОШЁЛСЯ → fail, exit 1 (дрейф после ревью)', () => {
      const r = evaluateReview('NEW', { date: '2026-07-01', catalog_hash: 'OLD' })
      expect(r.status).toBe('fail')
      expect(r.exitCode).toBe(1)
    })
  })

  describe('computeCatalogHash', () => {
    const list = () => ['common.json', 'nav.json', '.review-record.json', 'REVIEW.md']
    const read = (p: string) => `<<${p}>>`

    it('исключает dot-файлы и не-.json; детерминирован по сортировке', () => {
      const h1 = computeCatalogHash('/kz', list, read)
      // тот же набор в другом порядке листинга → тот же хэш (сортировка по имени)
      const h2 = computeCatalogHash('/kz', () => ['nav.json', '.review-record.json', 'common.json', 'REVIEW.md'], read)
      expect(h1).toBe(h2)
      expect(h1).toMatch(/^[0-9a-f]{64}$/)
    })

    it('изменение содержимого каталога → другой хэш', () => {
      const h1 = computeCatalogHash('/kz', list, read)
      const h2 = computeCatalogHash('/kz', list, (p) => (p.endsWith('common.json') ? 'CHANGED' : read(p)))
      expect(h1).not.toBe(h2)
    })
  })
})
