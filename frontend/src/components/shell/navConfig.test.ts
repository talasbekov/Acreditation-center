import { describe, it, expect } from 'vitest'
import { NAV_ITEMS, visibleNavItems } from './navConfig'

describe('navConfig (fe-2.2 AC-2/3)', () => {
  it('каждый пункт имеет ≥1 роль', () => {
    for (const item of NAV_ITEMS) {
      expect(item.roles.length).toBeGreaterThan(0)
    }
  })

  it('path уникальны', () => {
    const paths = NAV_ITEMS.map((i) => i.path)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('все key — в nav-namespace (nav:*)', () => {
    for (const item of NAV_ITEMS) {
      expect(item.key.startsWith('nav:')).toBe(true)
    }
  })

  it('роли реально фильтруют: оператор добавляет участников, проверяющие — нет', () => {
    const op = visibleNavItems('operator').map((i) => i.path)
    expect(op).toEqual(['/', '/add'])
    for (const role of ['superoperator', 'superuser']) {
      const paths = visibleNavItems(role).map((i) => i.path)
      expect(paths).toContain('/')
      expect(paths).not.toContain('/add')
      expect(paths.length).toBeLessThan(NAV_ITEMS.length)
    }
  })

  it('в меню только существующие страницы SPA (маршруты App.tsx)', () => {
    for (const item of NAV_ITEMS) {
      expect(['/', '/add']).toContain(item.path)
    }
  })

  // Сведение с этапами C–D: очередь проверки — Django-страница /review/<event>/
  // (eventproject/views/review.py), в SPA её нет — пункт меню не ведёт в пустоту.
  it('в SPA нет пунктов очереди проверки и инбокса возвратов', () => {
    for (const role of ['superuser', 'superoperator', 'operator']) {
      const paths = visibleNavItems(role).map((i) => i.path)
      expect(paths).not.toContain('/queue')
      expect(paths).not.toContain('/notifications')
    }
  })

  it('роль user / неизвестная / undefined → пустой nav (fail-closed)', () => {
    expect(visibleNavItems('user')).toHaveLength(0)
    expect(visibleNavItems('nonsense')).toHaveLength(0)
    expect(visibleNavItems(undefined)).toHaveLength(0)
  })
})
