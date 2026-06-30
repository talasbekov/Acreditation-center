/**
 * Story fe-3.1 — единый фронтовый источник проблемных флагов заявки.
 *
 * ⚠️ Зеркало backend `eventproject/problem_flags.py` (`PROBLEM_FLAGS`). Менять синхронно;
 * parity-тест `scripts/problem-flags-parity.test.ts` ловит дрейф. Закрытый набор —
 * DTO очереди проверки (fe-3.1) несёт подмножество. Лейблы — через i18n при рендере.
 */
export const PROBLEM_FLAGS = [
  'no_photo',
  'doc_unreadable',
  'photo_ratio',
  'duplicate_attendee',
  'iin_invalid',
] as const

export type ProblemFlag = (typeof PROBLEM_FLAGS)[number]
