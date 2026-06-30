import type { Role } from '@/types/role'

/**
 * Story fe-2.2 (AC-2) — единый источник правды для левой навигации.
 *
 * `key`   — i18n-ключ в `nav`-namespace (`t(item.key)`).
 * `path`  — route-target (`<NavLink to>`). Большинство целевых страниц — будущие истории
 *           (E3a+/hardening); AC проверяется на уровне href/route-target, не «приземления».
 * `roles` — разрешённые роли (строки backend: superuser/superoperator/operator/user).
 *
 * ⚠️ Маппинг персон дизайна (Admin/Superoperator/Operator) → роли backend — [ASSUMPTION];
 * сверять с RBAC-матрицей hd-7-1. Правка дешёвая — всё в одной таблице.
 *   superuser     ⇒ «Admin» (ревью/экспорт/аудит) — permissions.py: role == "superuser"
 *   superoperator ⇒ события/операторы/дашборд/импорт-триаж/агрегат участников
 *   operator      ⇒ свои участники/добавить/уведомления
 *   user          ⇒ без привилегий (пустой nav)
 */
export interface NavItem {
  key: string
  path: string
  roles: Role[]
}

export const NAV_ITEMS: NavItem[] = [
  // fe-3.2 (R6): выровнено под backend `IsSuperoperator` (= superoperator+superuser,
  // permissions.py:13) — иначе superoperator авторизован API очереди, но не видит пункт.
  { key: 'nav:queue', path: '/queue', roles: ['superuser', 'superoperator'] },
  { key: 'nav:events', path: '/events', roles: ['superuser', 'superoperator'] },
  { key: 'nav:attendees', path: '/', roles: ['operator', 'superoperator', 'superuser'] },
  { key: 'nav:add_attendee', path: '/add', roles: ['operator'] },
  { key: 'nav:operators', path: '/operators', roles: ['superoperator', 'superuser'] },
  { key: 'nav:export', path: '/export', roles: ['superuser'] },
  { key: 'nav:import_triage', path: '/import-triage', roles: ['superuser', 'superoperator'] },
  { key: 'nav:audit', path: '/audit', roles: ['superuser'] },
  { key: 'nav:notifications', path: '/notifications', roles: ['operator', 'superoperator', 'superuser'] },
  { key: 'nav:dashboard', path: '/dashboard', roles: ['superoperator'] },
]

/** Пункты, разрешённые роли. Неизвестная/без-привилегий роль → пустой список. */
export function visibleNavItems(role: string | undefined): NavItem[] {
  if (!role) return []
  return NAV_ITEMS.filter((item) => (item.roles as string[]).includes(role))
}
