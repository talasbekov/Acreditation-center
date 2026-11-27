import { z } from 'zod'
import { validateIIN } from './validateIIN'
import { KZ_COUNTRY_ID } from './constants'
import i18n from '@/i18n'

/** Сегодня в формате YYYY-MM-DD (локальная дата — как у `<input type="date">`). */
function today(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

const required = (message: string) => z.string().trim().min(1, message)

/**
 * Схема формы участника. Обязательные поля и проверки — как у HTML-формы
 * (`templates/gov3.html`, `views/attendee.py`); сервер проверяет то же самое.
 * ИИН (Story 5.2): клиент — `validateIIN` (порт iin.py), сервер — DRF-сериализатор.
 *
 * `checkDocDates` — даты документа и рождения проверяются при добавлении; при правке,
 * как и в HTML, участника с уже истёкшим документом можно поправить.
 */
export function makeAttendeeSchema({ checkDocDates = true }: { checkDocDates?: boolean } = {}) {
  return z
    .object({
      surname: required('Укажите фамилию'),
      firstname: required('Укажите имя'),
      patronymic: z.string(),
      transcription: required('Укажите имя латиницей'),
      birthDate: z.string().min(1, 'Укажите дату рождения'),
      sexId: z.string().min(1, 'Выберите пол'),
      post: required('Укажите должность'),
      countryId: z.string().min(1, 'Выберите страну'),
      iin: z.string(),
      stickId: z.string(),
      docTypeId: z.string().min(1, 'Выберите тип документа'),
      docSeries: z.string(),
      docNumber: required('Укажите номер документа'),
      docBegin: z.string().min(1, 'Укажите дату выдачи'),
      docEnd: z.string().min(1, 'Укажите, до какой даты действует документ'),
      docIssue: z.string(),
      request: z.string().regex(/^\d+$/, 'Выберите заявку'),
      visitObjects: required('Укажите объекты посещения'),
      // Story 5.3 — фото/документ. Для черновика необязательны; нужны для отправки
      // на проверку. Серверная Pillow-валидация (3×4, ≥600×800, ≤5МБ) — источник правды.
      photo: z.instanceof(File, { message: 'Некорректный файл фото' }).optional(),
      docScan: z.instanceof(File, { message: 'Некорректный файл документа' }).optional(),
    })
    .superRefine((data, ctx) => {
      const resident = data.countryId === KZ_COUNTRY_ID
      if (resident) {
        const iin = data.iin.trim()
        if (iin === '') {
          ctx.addIssue({ code: 'custom', path: ['iin'], message: 'Укажите ИИН резидента' })
        } else {
          const result = validateIIN(iin, data.birthDate)
          if (!result.valid) {
            ctx.addIssue({
              code: 'custom',
              path: ['iin'],
              // fe-1.4: validateIIN отдаёт код ошибки; текст — из каталога validation.
              message: i18n.t(`validation:${result.code ?? 'iin_invalid'}`, result.params),
            })
          }
        }
      } else if (data.stickId === '') {
        // Как в HTML-форме: категория нужна нерезиденту, у резидента её нет.
        ctx.addIssue({ code: 'custom', path: ['stickId'], message: 'Выберите категорию' })
      }
      if (checkDocDates) {
        const now = today()
        if (data.birthDate && data.birthDate > now) {
          ctx.addIssue({ code: 'custom', path: ['birthDate'], message: 'Проверьте дату рождения' })
        }
        if (data.docBegin && data.docBegin > now) {
          ctx.addIssue({ code: 'custom', path: ['docBegin'], message: 'Дата выдачи документа еще не наступила' })
        }
        if (data.docEnd && data.docEnd < now) {
          ctx.addIssue({ code: 'custom', path: ['docEnd'], message: 'Истек срок документа' })
        }
      }
    })
}

/** Схема добавления (с проверкой дат). */
export const attendeeSchema = makeAttendeeSchema()

export type AttendeeFormValues = z.infer<typeof attendeeSchema>
