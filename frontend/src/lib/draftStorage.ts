/**
 * Story 5.4 — безопасный слой автосохранения черновика формы участника.
 *
 * Best-effort: localStorage может быть недоступен (приватный режим Safari,
 * переполнение квоты, отключён политикой) → любая ошибка молча игнорируется,
 * форма продолжает работать. Сохраняются ТОЛЬКО текстовые поля; `File`
 * (photo/docScan) не сериализуется и не восстанавливается (AC-3).
 *
 * Ключ — единый на браузер (`attendee_draft_v1`): в форме нет селектора
 * события/категории (descope 5.2), поэтому event/category-scoped ключ из AC
 * недостижим; гранулярность вернётся вместе с селектором.
 */

export const DRAFT_KEY = 'attendee_draft_v1'

const DRAFT_FIELDS = [
  'surname',
  'firstname',
  'patronymic',
  'birthDate',
  'countryId',
  'iin',
  'request',
] as const

// «Значимые» поля для решения, показывать ли баннер восстановления: countryId
// исключён (у него непустой дефолт КЗ → иначе баннер всплывал бы на чистой форме).
const MEANINGFUL_FIELDS = [
  'surname',
  'firstname',
  'patronymic',
  'birthDate',
  'iin',
  'request',
] as const

export type AttendeeDraft = Partial<Record<(typeof DRAFT_FIELDS)[number], string>>

export function isMeaningfulDraft(data: Record<string, unknown> | null | undefined): boolean {
  if (!data) return false
  return MEANINGFUL_FIELDS.some((f) => {
    const v = data[f]
    return typeof v === 'string' && v.trim() !== ''
  })
}

export function saveDraft(data: Record<string, unknown>): void {
  try {
    const subset: AttendeeDraft = {}
    for (const f of DRAFT_FIELDS) {
      const v = data[f]
      if (typeof v === 'string') subset[f] = v // File/undefined отбрасываются
    }
    localStorage.setItem(DRAFT_KEY, JSON.stringify(subset))
  } catch {
    // best-effort: quota/приватный режим/disabled → no-op
  }
}

export function loadDraft(): AttendeeDraft | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    // Whitelist: только известные поля и только строки. Симметрично saveDraft —
    // иначе подделанный/устаревший черновик (`{iin:123}`) спредится в reset() и
    // уронит форму (`iin.trim is not a function`).
    const record = parsed as Record<string, unknown>
    const clean: AttendeeDraft = {}
    for (const f of DRAFT_FIELDS) {
      const v = record[f]
      if (typeof v === 'string') clean[f] = v
    }
    return clean
  } catch {
    // битый JSON → чистим мусор и считаем, что черновика нет
    try {
      localStorage.removeItem(DRAFT_KEY)
    } catch {
      /* no-op */
    }
    return null
  }
}

export function clearDraft(): void {
  try {
    localStorage.removeItem(DRAFT_KEY)
  } catch {
    /* no-op */
  }
}

export function hasDraft(): boolean {
  return isMeaningfulDraft(loadDraft())
}
