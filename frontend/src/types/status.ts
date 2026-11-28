/**
 * Story fe-2.4 — единый источник статусов участника на фронте.
 *
 * ⚠️ Зеркало backend `eventproject/state_machine.py` (`ATTENDEE_STATUSES`). Менять синхронно
 * с ним. Лейблы — через i18n `status`-namespace (`t('status:<code>')`).
 */
export const ATTENDEE_STATUSES = ['draft', 'submitted', 'in_review', 'ready', 'exported'] as const

export type AttendeeStatus = (typeof ATTENDEE_STATUSES)[number]
