import { z } from 'zod'
import { validateIIN } from './validateIIN'
import { encodeValidationError } from './validationError'
import { KZ_COUNTRY_ID } from './constants'

/**
 * Схема формы участника. Двойная валидация ИИН (Story 5.2): zod-клиент (здесь) +
 * DRF-сериализатор (сервер). Для резидента (countryId === KZ) ИИН обязателен и
 * проверяется `validateIIN` (порт iin.py). Для нерезидента ИИН не требуется.
 *
 * fe-1.4: `message` каждого правила — i18n-КЛЮЧ (`validation:*`), не ru-строка. Форма
 * рендерит t(message) через translateFieldError. Ключ ИИН с параметрами кодируется
 * (encodeValidationError) — RHF несёт только строку.
 */
export const attendeeSchema = z
  .object({
    surname: z.string().trim().min(1, 'validation:required_surname'),
    firstname: z.string().trim().min(1, 'validation:required_firstname'),
    patronymic: z.string(),
    birthDate: z.string().min(1, 'validation:required_birthdate'),
    countryId: z.string().min(1, 'validation:required_country'),
    iin: z.string(),
    request: z.string().regex(/^\d+$/, 'validation:required_category'),
    // Story 5.3 — фото/документ. Опциональны (модель blank=True); серверная
    // Pillow-валидация (3×4, ≥600×800, ≤5МБ) — источник правды.
    photo: z.instanceof(File, { message: 'validation:invalid_photo' }).optional(),
    docScan: z.instanceof(File, { message: 'validation:invalid_docscan' }).optional(),
  })
  .superRefine((data, ctx) => {
    if (data.countryId === KZ_COUNTRY_ID) {
      const iin = data.iin.trim()
      if (iin === '') {
        ctx.addIssue({
          code: 'custom',
          path: ['iin'],
          message: 'validation:iin_required_resident',
        })
        return
      }
      const result = validateIIN(iin, data.birthDate)
      if (!result.valid) {
        const key = result.code ? `validation:${result.code}` : 'validation:iin_invalid'
        ctx.addIssue({
          code: 'custom',
          path: ['iin'],
          message: encodeValidationError(key, result.params),
        })
      }
    }
  })

export type AttendeeFormValues = z.infer<typeof attendeeSchema>
