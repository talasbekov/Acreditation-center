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

// Только существующие страницы SPA. Мероприятия, операторы, выгрузка, журнал и очередь
// проверки — Django-страницы (этапы C–D); пункт меню без страницы вёл бы на главную.
export const NAV_ITEMS: NavItem[] = [
  { key: 'nav:attendees', path: '/', roles: ['operator', 'superoperator', 'superuser'] },
  { key: 'nav:add_attendee', path: '/add', roles: ['operator'] },
]

/** Пункты, разрешённые роли. Неизвестная/без-привилегий роль → пустой список. */
export function visibleNavItems(role: string | undefined): NavItem[] {
  if (!role) return []
  return NAV_ITEMS.filter((item) => (item.roles as string[]).includes(role))
}
