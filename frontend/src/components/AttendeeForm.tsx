import { useEffect, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import { attendeeSchema, type AttendeeFormValues } from '@/lib/attendeeSchema'
import { KZ_COUNTRY_ID } from '@/lib/constants'
import { apiFetch, ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'

const SERVER_FIELDS: ReadonlySet<string> = new Set([
  'surname',
  'firstname',
  'patronymic',
  'birthDate',
  'countryId',
  'iin',
  'request',
])

/**
 * Форма добавления участника (Story 5.2): real-time ИИН-валидация (onChange,
 * без debounce), residency switch (страна ≠ КЗ → ИИН скрыт), submit на DRF с
 * CSRF, toast, маппинг RFC7807 ошибок на поля.
 */
export function AttendeeForm() {
  const {
    register,
    handleSubmit,
    watch,
    reset,
    setError,
    trigger,
    formState: { errors, isSubmitting },
  } = useForm<AttendeeFormValues>({
    resolver: zodResolver(attendeeSchema),
    mode: 'onChange',
    defaultValues: {
      surname: '',
      firstname: '',
      patronymic: '',
      birthDate: '',
      countryId: KZ_COUNTRY_ID,
      iin: '',
      request: '',
    },
  })

  const countryId = watch('countryId')
  const iin = watch('iin')
  const birthDate = watch('birthDate')
  const isResident = countryId === KZ_COUNTRY_ID
  const iinLooksValid = isResident && iin.trim() !== '' && !errors.iin

  // Cross-field: при изменении даты рождения перевалидировать ИИН (RHF по умолчанию
  // ревалидирует только изменённое поле → иначе ошибка несовпадения устаревает).
  useEffect(() => {
    if (isResident && iin.trim() !== '') void trigger('iin')
  }, [birthDate, isResident, iin, trigger])

  async function onSubmit(values: AttendeeFormValues) {
    const payload = {
      surname: values.surname,
      firstname: values.firstname,
      patronymic: values.patronymic,
      birthDate: values.birthDate,
      countryId: values.countryId,
      request: Number(values.request),
      // Нерезидент — ИИН не отправляем (сервер выведет is_resident из countryId).
      iin: isResident ? values.iin.trim() : '',
    }
    try {
      await apiFetch('/api/v1/attendees/', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      toast.success('Участник добавлен')
      reset()
    } catch (e) {
      if (e instanceof ApiError) {
        const field = e.problem?.field
        const message = e.problem?.detail ?? e.problem?.title ?? 'Ошибка сохранения'
        // ИИН-поле скрыто у нерезидента — setError на нём был бы невидим → toast.
        const fieldHidden = field === 'iin' && !isResident
        if (field && SERVER_FIELDS.has(field) && !fieldHidden) {
          setError(field as keyof AttendeeFormValues, { message })
        } else {
          toast.error(message)
        }
      } else {
        toast.error('Сеть недоступна. Повторите.')
      }
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field label="Фамилия" error={errors.surname?.message}>
        <input id="surname" className={inputCls} {...register('surname')} />
      </Field>
      <Field label="Имя" error={errors.firstname?.message}>
        <input id="firstname" className={inputCls} {...register('firstname')} />
      </Field>
      <Field label="Отчество" error={errors.patronymic?.message}>
        <input id="patronymic" className={inputCls} {...register('patronymic')} />
      </Field>
      <Field label="Дата рождения" error={errors.birthDate?.message}>
        <input id="birthDate" type="date" className={inputCls} {...register('birthDate')} />
      </Field>

      <Field label="Страна" error={errors.countryId?.message}>
        <select id="countryId" className={inputCls} {...register('countryId')}>
          <option value={KZ_COUNTRY_ID}>Казахстан (резидент)</option>
          <option value="643">Другая страна (нерезидент)</option>
        </select>
      </Field>

      {isResident && (
        <Field label="ИИН" error={errors.iin?.message}>
          <div className="flex items-center gap-2">
            <input
              id="iin"
              inputMode="numeric"
              maxLength={12}
              aria-invalid={errors.iin ? true : undefined}
              className={`${inputCls} ${errors.iin ? 'border-red-600' : ''}`}
              {...register('iin')}
            />
            {iinLooksValid && (
              <span aria-label="ИИН корректен" className="text-green-600 text-xl">
                ✅
              </span>
            )}
          </div>
        </Field>
      )}

      <Field label="Категория (ID мероприятия)" error={errors.request?.message}>
        <input id="request" inputMode="numeric" className={inputCls} {...register('request')} />
      </Field>

      <Button type="submit" disabled={isSubmitting}>
        Сохранить
      </Button>
    </form>
  )
}

const inputCls =
  'w-full rounded-md border border-neutral-400 px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-700'

function Field({
  label,
  error,
  children,
}: {
  label: string
  error?: string
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-neutral-900">{label}</span>
      {children}
      {error && (
        <p role="alert" className="mt-1 text-sm text-red-600">
          {error}
        </p>
      )}
    </label>
  )
}
