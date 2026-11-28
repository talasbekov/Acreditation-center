import { z } from 'zod'
import { validateIIN } from './validateIIN'
import { KZ_COUNTRY_ID } from './constants'
import { encodeValidationError } from './validationError'

/** Сегодня в формате YYYY-MM-DD (локальная дата — как у `<input type="date">`). */
function today(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

const required = (key: string) => z.string().trim().min(1, key)

/**
 * Схема формы участника. Обязательные поля и проверки — как у HTML-формы
 * (`templates/gov3.html`, `views/attendee.py`); сервер проверяет то же самое.
 * ИИН (Story 5.2): клиент — `validateIIN` (порт iin.py), сервер — DRF-сериализатор.
 *
 * fe-1.4: `message` каждого правила — i18n-ключ (`validation:*`), не готовый текст.
 * Форма переводит его при показе (`translateFieldError`), поэтому сообщение меняется
 * вместе с языком. Ключ ИИН с параметрами кодируется `encodeValidationError`.
 *
 * `checkDocDates` — даты документа и рождения проверяются при добавлении; при правке,
 * как и в HTML, участника с уже истёкшим документом можно поправить.
 */
export function makeAttendeeSchema({ checkDocDates = true }: { checkDocDates?: boolean } = {}) {
  return z
    .object({
      surname: required('validation:required_surname'),
      firstname: required('validation:required_firstname'),
      patronymic: z.string(),
      transcription: required('validation:required_transcription'),
      birthDate: z.string().min(1, 'validation:required_birthdate'),
      sexId: z.string().min(1, 'validation:required_sex'),
      post: required('validation:required_post'),
      countryId: z.string().min(1, 'validation:required_country'),
      iin: z.string(),
      stickId: z.string(),
      docTypeId: z.string().min(1, 'validation:required_doc_type'),
      docSeries: z.string(),
      docNumber: required('validation:required_doc_number'),
      docBegin: z.string().min(1, 'validation:required_doc_begin'),
      docEnd: z.string().min(1, 'validation:required_doc_end'),
      docIssue: z.string(),
      request: z.string().regex(/^\d+$/, 'validation:required_request'),
      visitObjects: required('validation:required_visit_objects'),
      // Story 5.3 — фото/документ. Для черновика необязательны; нужны для отправки
      // на проверку. Серверная Pillow-валидация (3×4, ≥600×800, ≤5МБ) — источник правды.
      photo: z.instanceof(File, { message: 'validation:invalid_photo' }).optional(),
      docScan: z.instanceof(File, { message: 'validation:invalid_docscan' }).optional(),
    })
    .superRefine((data, ctx) => {
      const resident = data.countryId === KZ_COUNTRY_ID
      if (resident) {
        const iin = data.iin.trim()
        if (iin === '') {
          ctx.addIssue({ code: 'custom', path: ['iin'], message: 'validation:iin_required_resident' })
        } else {
          const result = validateIIN(iin, data.birthDate)
          if (!result.valid) {
            const key = result.code ? `validation:${result.code}` : 'validation:iin_invalid'
            ctx.addIssue({ code: 'custom', path: ['iin'], message: encodeValidationError(key, result.params) })
          }
        }
      } else if (data.stickId === '') {
        // Как в HTML-форме: категория нужна нерезиденту, у резидента её нет.
        ctx.addIssue({ code: 'custom', path: ['stickId'], message: 'validation:required_stick' })
      }
      if (checkDocDates) {
        const now = today()
        if (data.birthDate && data.birthDate > now) {
          ctx.addIssue({ code: 'custom', path: ['birthDate'], message: 'validation:birthdate_future' })
        }
        if (data.docBegin && data.docBegin > now) {
          ctx.addIssue({ code: 'custom', path: ['docBegin'], message: 'validation:doc_begin_future' })
        }
        if (data.docEnd && data.docEnd < now) {
          ctx.addIssue({ code: 'custom', path: ['docEnd'], message: 'validation:doc_expired' })
        }
      }
    })
}

/** Схема добавления (с проверкой дат). */
export const attendeeSchema = makeAttendeeSchema()

export type AttendeeFormValues = z.infer<typeof attendeeSchema>
