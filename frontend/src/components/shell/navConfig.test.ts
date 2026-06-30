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

  it('роли реально фильтруют: operator видит подмножество, не весь список', () => {
    const op = visibleNavItems('operator')
    expect(op.length).toBeGreaterThan(0)
    expect(op.length).toBeLessThan(NAV_ITEMS.length)
    // admin-only пункты недоступны оператору
    expect(op.find((i) => i.path === '/audit')).toBeUndefined()
    expect(op.find((i) => i.path === '/export')).toBeUndefined()
    // свои — доступны
    expect(op.find((i) => i.path === '/')).toBeDefined()
    expect(op.find((i) => i.path === '/add')).toBeDefined()
  })

  it('superuser видит admin-only пункты (audit/export/queue)', () => {
    const su = visibleNavItems('superuser')
    expect(su.find((i) => i.path === '/audit')).toBeDefined()
    expect(su.find((i) => i.path === '/export')).toBeDefined()
    expect(su.find((i) => i.path === '/queue')).toBeDefined()
  })

  // fe-3.2 (AC-6 / R6): очередь проверки выровнена под backend IsSuperoperator
  // (= superoperator+superuser, permissions.py:13). superoperator ОБЯЗАН видеть /queue;
  // operator/user — нет (queue = admin-агрегат).
  it('superoperator видит /queue (выравнивание под backend IsSuperoperator)', () => {
    const so = visibleNavItems('superoperator')
    expect(so.find((i) => i.path === '/queue')).toBeDefined()
  })

  it('operator не видит /queue (admin-агрегат)', () => {
    expect(visibleNavItems('operator').find((i) => i.path === '/queue')).toBeUndefined()
  })

  it('роль user / неизвестная / undefined → пустой nav (fail-closed)', () => {
    expect(visibleNavItems('user')).toHaveLength(0)
    expect(visibleNavItems('nonsense')).toHaveLength(0)
    expect(visibleNavItems(undefined)).toHaveLength(0)
  })
})
