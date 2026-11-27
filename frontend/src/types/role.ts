/**
 * Story fe-2.2 — роли пользователя (источник: backend `Operator.ROLE_CHOICES` +
 * `User.role` property, eventproject/models.py). Приходят строкой от
 * `GET /api/v1/rbac-check/` → `{ role }` (см. api/auth.ts `checkSession`).
 */
export type Role = 'superuser' | 'superoperator' | 'operator' | 'user'
