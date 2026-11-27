import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { makeAttendeeSchema, type AttendeeFormValues } from '@/lib/attendeeSchema'
import { KZ_COUNTRY_ID } from '@/lib/constants'
import { apiFetch, ApiError } from '@/api/client'
import { getDirectories, type DirectoryRow } from '@/api/directories'
import { getRequests } from '@/api/requests'
import { Button } from '@/components/ui/button'
import { ErrorSummary, Field, FormSection, describedBy, fieldClass, type SummaryItem } from '@/components/ui/form'
import { PhotoUpload } from '@/components/PhotoUpload/PhotoUpload'
import { DocumentUpload } from '@/components/DocumentUpload/DocumentUpload'

type FieldName = keyof AttendeeFormValues

const DEFAULT_VALUES: AttendeeFormValues = {
  surname: '',
  firstname: '',
  patronymic: '',
  transcription: '',
  birthDate: '',
  sexId: '',
  post: '',
  countryId: KZ_COUNTRY_ID,
  iin: '',
  stickId: '',
  docTypeId: '',
  docSeries: '',
  docNumber: '',
  docBegin: '',
  docEnd: '',
  docIssue: '',
  request: '',
  visitObjects: '',
  photo: undefined,
  docScan: undefined,
}

/** Подписи полей — и для меток, и для сводки ошибок. Порядок — порядок на экране. */
const LABELS: Record<FieldName, string> = {
  surname: 'Фамилия',
  firstname: 'Имя',
  patronymic: 'Отчество',
  transcription: 'Имя латиницей',
  birthDate: 'Дата рождения',
  sexId: 'Пол',
  post: 'Должность',
  countryId: 'Гражданство',
  iin: 'ИИН',
  stickId: 'Категория',
  docTypeId: 'Тип документа',
  docSeries: 'Серия',
  docNumber: 'Номер документа',
  docBegin: 'Дата выдачи',
  docEnd: 'Действителен до',
  docIssue: 'Кем выдан',
  request: 'Заявка',
  visitObjects: 'Объекты посещения',
  photo: 'Фото участника',
  docScan: 'Скан документа',
}
const FIELD_ORDER = Object.keys(LABELS) as FieldName[]
const SERVER_FIELDS: ReadonlySet<string> = new Set(FIELD_ORDER)

/** Поля-справочники: после загрузки списков значение возвращается в `<select>`. */
const SELECT_FIELDS: FieldName[] = ['request', 'countryId', 'sexId', 'docTypeId', 'stickId']

export interface AttendeeFormProps {
  /** Story 5.5: задан → режим РЕДАКТИРОВАНИЯ (PATCH /{id}/), иначе — добавление (POST). */
  attendeeId?: number
  /** Story 5.5: предзаполнение полей (edit). */
  initialValues?: Partial<AttendeeFormValues>
  /** Story 5.5: только чтение (статус ready/exported) — поля заблокированы. */
  readOnly?: boolean
  /** P2-7: URL уже загруженного фото (edit) — превью до выбора нового файла. */
  initialPhotoUrl?: string | null
  /** P2-7: URL уже загруженного документа (edit). */
  initialDocScanUrl?: string | null
  /** Этап D: ссылка «Отмена» рядом с кнопкой сохранения (страница передаёт Link). */
  cancel?: ReactNode
}

export function AttendeeForm({
  attendeeId,
  initialValues,
  readOnly = false,
  initialPhotoUrl,
  initialDocScanUrl,
  cancel,
}: AttendeeFormProps = {}) {
  const isEdit = attendeeId !== undefined
  const queryClient = useQueryClient()
  // Даты документа проверяются при добавлении; правка, как в HTML, их не перепроверяет.
  const schema = useMemo(() => makeAttendeeSchema({ checkDocDates: !isEdit }), [isEdit])
  const {
    register,
    handleSubmit,
    watch,
    reset,
    setError,
    setValue,
    getValues,
    trigger,
    formState: { errors, isSubmitting },
  } = useForm<AttendeeFormValues>({
    resolver: zodResolver(schema),
    mode: 'onChange',
    defaultValues: { ...DEFAULT_VALUES, ...initialValues },
  })

  const countryId = watch('countryId')
  const iin = watch('iin')
  const birthDate = watch('birthDate')
  const photo = watch('photo')
  const docScan = watch('docScan')
  const currentRequest = watch('request')
  const isResident = countryId === KZ_COUNTRY_ID
  // Сводка ошибок появляется после попытки сохранить и объявляется диктору
  // (role=alert); фокус react-hook-form сам ставит на первое поле с ошибкой.
  const [summaryRequested, setSummaryRequested] = useState(0)
  const iinLooksValid = isResident && iin.trim() !== '' && !errors.iin

  // FE-1: RBAC-scoped список заявок. В правке поле заблокировано (P2-6), но список
  // нужен и там — показать название заявки и мероприятия, а не «#id».
  const { data: requestOptions = [] } = useQuery({
    queryKey: ['requests'],
    queryFn: getRequests,
    staleTime: 5 * 60_000,
  })
  // Этап D: справочники пола, типов документов, категорий и стран (как у HTML-формы).
  const { data: dirs, isError: dirsError } = useQuery({
    queryKey: ['directories'],
    queryFn: getDirectories,
    staleTime: 30 * 60_000,
  })
  // Списки приходят после предзаполнения: опции <select> меняются, и браузер теряет
  // выбранное значение (поле показывало пустой вариант). Возвращаем значения явно.
  useEffect(() => {
    for (const name of SELECT_FIELDS) {
      const value = getValues(name)
      if (value) setValue(name, value)
    }
  }, [requestOptions, dirs, getValues, setValue])
  const currentRequestInList = requestOptions.some((r) => String(r.id) === String(currentRequest))

  // Cross-field: при изменении даты рождения перевалидировать ИИН (RHF по умолчанию
  // ревалидирует только изменённое поле → иначе ошибка несовпадения устаревает).
  useEffect(() => {
    if (isResident && iin.trim() !== '') void trigger('iin')
  }, [birthDate, isResident, iin, trigger])

  async function onSubmit(values: AttendeeFormValues) {
    // Story 5.3: multipart (фото/документ — файлы). apiFetch НЕ ставит JSON
    // Content-Type для non-string body → браузер сам выставит multipart boundary.
    const fd = new FormData()
    for (const name of FIELD_ORDER) {
      if (name === 'photo' || name === 'docScan' || name === 'iin' || name === 'stickId') continue
      fd.append(name, String(values[name] ?? '').trim())
    }
    // Нерезидент — ИИН не отправляем; резиденту категория не нужна (как в HTML).
    fd.append('iin', isResident ? values.iin.trim() : '')
    fd.append('stickId', isResident ? '' : values.stickId)
    if (values.photo) fd.append('photo', values.photo)
    if (values.docScan) fd.append('docScan', values.docScan)
    try {
      await apiFetch(isEdit ? `/api/v1/attendees/${attendeeId}/` : '/api/v1/attendees/', {
        method: isEdit ? 'PATCH' : 'POST',
        body: fd,
      })
      // AC-6: обновляем кэш списка участников после мутации.
      void queryClient.invalidateQueries({ queryKey: ['attendees'] })
      if (isEdit) {
        // Edit: инвалидируем и detail-кэш (EditAttendeePage: ['attendee', id]).
        void queryClient.invalidateQueries({ queryKey: ['attendee', attendeeId] })
        toast.success('Изменения сохранены')
      } else {
        toast.success('Участник добавлен')
        reset()
        setSummaryRequested(0)
      }
    } catch (e) {
      if (e instanceof ApiError) {
        // Этап D: сервер отдаёт ошибки по каждому полю (`errors`); прежний формат —
        // одно поле `field` с текстом в `detail`.
        const problem = e.problem
        const byField = problem?.errors ?? (problem?.field ? { [problem.field]: problem.detail ?? '' } : {})
        let shown = 0
        for (const [field, message] of Object.entries(byField)) {
          // ИИН скрыт у нерезидента, категория — у резидента: ошибка там была бы невидима.
          const hidden = (field === 'iin' && !isResident) || (field === 'stickId' && isResident)
          if (SERVER_FIELDS.has(field) && !hidden) {
            setError(field as FieldName, { message: message || 'Неверное значение' })
            shown += 1
          }
        }
        if (shown > 0) setSummaryRequested((n) => n + 1)
        else toast.error(problem?.detail ?? problem?.title ?? 'Ошибка сохранения')
      } else {
        toast.error('Сеть недоступна. Повторите.')
      }
    }
  }

  const summaryItems: SummaryItem[] = FIELD_ORDER.filter((name) => errors[name]?.message).map((name) => ({
    id: name,
    label: LABELS[name],
    message: String(errors[name]?.message),
  }))

  /** Атрибуты доступности поля: обязательность, ошибка, подсказка. */
  function a11y(name: FieldName, opts: { required?: boolean; hint?: boolean } = {}) {
    return {
      id: name,
      'aria-required': opts.required ? ('true' as const) : undefined,
      'aria-invalid': errors[name] ? true : undefined,
      'aria-describedby': describedBy(name, opts.hint ? 'hint' : undefined, errors[name]?.message),
      className: fieldClass(Boolean(errors[name])),
    }
  }

  function text(name: FieldName, opts: { required?: boolean; hint?: string; wide?: boolean; inputMode?: 'numeric' } = {}) {
    return (
      <Field id={name} label={LABELS[name]} required={opts.required} hint={opts.hint} wide={opts.wide} error={errors[name]?.message}>
        <input inputMode={opts.inputMode} {...a11y(name, { required: opts.required, hint: Boolean(opts.hint) })} {...register(name)} />
      </Field>
    )
  }

  function dateField(name: FieldName, required = true) {
    return (
      <Field id={name} label={LABELS[name]} required={required} error={errors[name]?.message}>
        <input type="date" {...a11y(name, { required })} {...register(name)} />
      </Field>
    )
  }

  function select(name: FieldName, rows: DirectoryRow[] | undefined, opts: { required?: boolean; hint?: string; placeholder: string }) {
    return (
      <Field id={name} label={LABELS[name]} required={opts.required} hint={opts.hint} error={errors[name]?.message}>
        <DirectorySelect
          rows={rows}
          placeholder={opts.placeholder}
          current={String(getValues(name) ?? '')}
          attrs={a11y(name, { required: opts.required, hint: Boolean(opts.hint) })}
          registration={register(name)}
        />
      </Field>
    )
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit, () => setSummaryRequested((n) => n + 1))}
      className="space-y-4"
      autoComplete="off"
      noValidate
    >
      {summaryRequested > 0 && summaryItems.length > 0 && <ErrorSummary items={summaryItems} />}

      {!readOnly && (
        <p className="text-sm leading-5 text-ink-2">
          До сохранения данные доступны только в открытой форме. При уходе со страницы изменения потеряются.
          Поля со звёздочкой <span className="font-semibold text-danger">*</span> обязательны.
        </p>
      )}
      {readOnly && (
        <div role="alert" className="rounded-lg bg-info-bg p-4 text-info">
          <p className="font-semibold">Редактирование заблокировано</p>
          <p className="mt-1 text-sm leading-5">Участник отправлен на проверку или допущен. Данные открыты только для чтения.</p>
        </div>
      )}
      {dirsError && (
        <p role="alert" className="rounded-lg bg-warning-bg p-4 text-sm leading-5 font-semibold text-warning">
          Не удалось загрузить справочники (пол, документы, страны). Обновите страницу.
        </p>
      )}

      <fieldset disabled={readOnly} className="m-0 space-y-4 border-0 p-0">
        <FormSection title="Основные сведения">
          {text('surname', { required: true })}
          {text('firstname', { required: true })}
          {text('patronymic', { hint: 'Если есть' })}
          {text('transcription', { required: true, hint: 'Фамилия и имя латиницей, как в документе' })}
          {dateField('birthDate')}
          {select('sexId', dirs?.sexes, { required: true, placeholder: '— выберите —' })}
          {text('post', { required: true, wide: true })}
        </FormSection>

        <FormSection title="Гражданство" description="ИИН нужен гражданам Казахстана, категория — гражданам других стран.">
          {select('countryId', dirs?.countries, { required: true, placeholder: '— выберите страну —' })}
          {isResident ? (
            <Field
              id="iin"
              label="ИИН"
              required
              hint={iinLooksValid ? undefined : '12 цифр; дата рождения в ИИН должна совпадать с указанной'}
              error={errors.iin?.message}
            >
              <input inputMode="numeric" maxLength={12} {...a11y('iin', { required: true, hint: !iinLooksValid })} {...register('iin')} />
              {iinLooksValid && (
                <p role="status" className="mt-1 text-sm leading-5 font-semibold text-success">
                  ✓ Формат ИИН верный
                </p>
              )}
            </Field>
          ) : (
            select('stickId', dirs?.categories, { required: true, placeholder: '— выберите категорию —' })
          )}
        </FormSection>

        <FormSection title="Документ">
          {select('docTypeId', dirs?.document_types, { required: true, placeholder: '— выберите тип —' })}
          {text('docSeries', { hint: 'Если есть' })}
          {text('docNumber', { required: true })}
          {text('docIssue', { hint: 'Если указано в документе' })}
          {dateField('docBegin')}
          {dateField('docEnd')}
        </FormSection>

        <FormSection title="Заявка и посещение">
          <Field
            id="request"
            label="Заявка"
            required={!isEdit}
            wide
            hint={isEdit ? 'Участника нельзя перенести в другую заявку.' : 'Заявка определяет мероприятие участника.'}
            error={errors.request?.message}
          >
            {/* FE-1: выбор из RBAC-scoped списка. P2-6: в правке поле заблокировано. */}
            <select
              disabled={isEdit || readOnly}
              aria-readonly={isEdit || undefined}
              {...a11y('request', { required: !isEdit, hint: true })}
              {...register('request')}
            >
              <option value="">— выберите заявку —</option>
              {requestOptions.map((r) => (
                <option key={r.id} value={String(r.id)}>
                  {r.name} — {r.event_name}
                </option>
              ))}
              {currentRequest && !currentRequestInList && <option value={String(currentRequest)}>Заявка #{currentRequest}</option>}
            </select>
          </Field>
          {text('visitObjects', { required: true, wide: true, hint: 'Залы и объекты, куда нужен доступ' })}
        </FormSection>

        <FormSection title="Файлы" description="Фото и скан нужны для отправки на проверку. Сохранить черновик можно и без них.">
          {/* Story 5.3 — физически разделённые зоны фото/документа с превью. */}
          <PhotoUpload
            file={photo ?? null}
            existingUrl={initialPhotoUrl}
            onFileChange={(f) => setValue('photo', f ?? undefined, { shouldValidate: true })}
            error={errors.photo?.message}
          />
          <DocumentUpload
            file={docScan ?? null}
            existingUrl={initialDocScanUrl}
            onFileChange={(f) => setValue('docScan', f ?? undefined, { shouldValidate: true })}
            error={errors.docScan?.message}
          />
        </FormSection>

        {!readOnly && (
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button variant="primary" type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Сохранение…' : isEdit ? 'Сохранить изменения' : 'Сохранить'}
            </Button>
            {cancel}
          </div>
        )}
      </fieldset>
    </form>
  )
}

/**
 * `<select>` справочника. Пока список не загружен, а также если сохранённого кода нет
 * в справочнике (старые данные), текущее значение остаётся отдельной опцией —
 * поле не сбрасывается молча.
 */
function DirectorySelect({
  rows,
  placeholder,
  current,
  attrs,
  registration,
}: {
  rows: DirectoryRow[] | undefined
  placeholder: string
  current: string
  attrs: Record<string, unknown>
  registration: UseFormRegisterReturn
}) {
  const known = rows?.some((r) => r.code === current)
  return (
    <select {...attrs} {...registration}>
      <option value="">{rows ? placeholder : 'Загрузка…'}</option>
      {rows?.map((r) => (
        <option key={r.code} value={r.code}>
          {r.name}
        </option>
      ))}
      {current && !known && <option value={current}>Код {current}</option>}
    </select>
  )
}
