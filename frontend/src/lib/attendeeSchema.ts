import { z } from 'zod'
import { validateIIN } from './validateIIN'
import { KZ_COUNTRY_ID } from './constants'

/**
 * Схема формы участника. Двойная валидация ИИН (Story 5.2): zod-клиент (здесь) +
 * DRF-сериализатор (сервер). Для резидента (countryId === KZ) ИИН обязателен и
 * проверяется `validateIIN` (порт iin.py). Для нерезидента ИИН не требуется.
 */
export const attendeeSchema = z
  .object({
    surname: z.string().trim().min(1, 'Укажите фамилию'),
    firstname: z.string().trim().min(1, 'Укажите имя'),
    patronymic: z.string(),
    birthDate: z.string().min(1, 'Укажите дату рождения'),
    countryId: z.string().min(1, 'Выберите страну'),
    iin: z.string(),
    request: z.string().regex(/^\d+$/, 'Укажите категорию (ID мероприятия)'),
    // Story 5.3 — фото/документ. Опциональны (модель blank=True); серверная
    // Pillow-валидация (3×4, ≥600×800, ≤5МБ) — источник правды.
    photo: z.instanceof(File, { message: 'Некорректный файл фото' }).optional(),
    docScan: z.instanceof(File, { message: 'Некорректный файл документа' }).optional(),
  })
  .superRefine((data, ctx) => {
    if (data.countryId === KZ_COUNTRY_ID) {
      const iin = data.iin.trim()
      if (iin === '') {
        ctx.addIssue({
          code: 'custom',
          path: ['iin'],
          message: 'Укажите ИИН резидента',
        })
        return
      }
      const result = validateIIN(iin, data.birthDate)
      if (!result.valid) {
        ctx.addIssue({
          code: 'custom',
          path: ['iin'],
          message: result.error ?? 'Неверный ИИН',
        })
      }
    }
  })

export type AttendeeFormValues = z.infer<typeof attendeeSchema>
