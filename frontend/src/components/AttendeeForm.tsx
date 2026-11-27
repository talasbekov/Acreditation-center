import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { makeAttendeeSchema, type AttendeeFormValues } from '@/lib/attendeeSchema'
import { KZ_COUNTRY_ID } from '@/lib/constants'
import { translateFieldError } from '@/lib/validationError'
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

/** Порядок полей на экране — он же порядок сводки ошибок. Подписи — `operatorForm:label.*`. */
const FIELD_ORDER: FieldName[] = [
  'surname',
  'firstname',
  'patronymic',
  'transcription',
  'birthDate',
  'sexId',
  'post',
  'countryId',
  'iin',
  'stickId',
  'docTypeId',
  'docSeries',
  'docNumber',
  'docIssue',
  'docBegin',
  'docEnd',
  'request',
  'visitObjects',
  'photo',
  'docScan',
]
const SERVER_FIELDS: ReadonlySet<string> = new Set(FIELD_ORDER)

/** Поля-справочники: после загрузки списков значение возвращается в `<select>`. */
const SELECT_FIELDS: FieldName[] = ['request', 'countryId', 'sexId', 'docTypeId', 'stickId']

/**
 * fe-2.7: проверка ИИН идёт на каждый ввод, а диктору объявляется итог после паузы —
 * иначе при наборе 12 цифр он прочитал бы 12 сообщений.
 */
const IIN_ANNOUNCE_DELAY_MS = 500

function useSettled<T>(value: T, delay: number): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return settled
}

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
  const { t } = useTranslation()
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
    formState: { errors, isSubmitting, submitCount },
  } = useForm<AttendeeFormValues>({
    resolver: zodResolver(schema),
    mode: 'onChange',
    defaultValues: { ...DEFAULT_VALUES, ...initialValues },
  })

  /** Текст ошибки поля на языке интерфейса (ключ схемы или готовый текст сервера). */
  const errorText = (name: FieldName) => translateFieldError(t, errors[name]?.message)
  const label = (name: FieldName) => t(`operatorForm:label.${name}`)

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
  const iinFilled = isResident && iin.trim() !== ''
  const iinError = errorText('iin')
  const iinLooksValid = iinFilled && !errors.iin
  // До первой попытки сохранить ошибку ИИН сообщает живой регион (после паузы);
  // после — сама подпись поля, как у остальных полей.
  const iinLive = useSettled(
    !iinFilled || submitCount > 0 ? '' : iinError ?? t('operatorForm:iin_valid'),
    IIN_ANNOUNCE_DELAY_MS,
  )

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
        toast.success(t('operatorForm:toast.updated'))
      } else {
        toast.success(t('operatorForm:toast.added'))
        reset()
        setSummaryRequested(0)
      }
    } catch (e) {
      if (e instanceof ApiError) {
        // Ошибки по полям: код ошибки (`type`) переводится каталогом `errors`, когда
        // ошибка одна и её поле известно; иначе — текст сервера из `errors` (этап D).
        const problem = e.problem
        // `unknown` — код без перевода (сервер не пометил ошибку): тогда показываем его текст.
        const coded =
          problem?.type && problem.type !== 'unknown' && problem.field
            ? t(`errors:${problem.type}`, { ...problem.params, defaultValue: '' })
            : ''
        const byField = problem?.errors ?? (problem?.field ? { [problem.field]: problem.detail ?? '' } : {})
        let shown = 0
        for (const [field, message] of Object.entries(byField)) {
          // ИИН скрыт у нерезидента, категория — у резидента: ошибка там была бы невидима.
          const hidden = (field === 'iin' && !isResident) || (field === 'stickId' && isResident)
          if (SERVER_FIELDS.has(field) && !hidden) {
            const text = field === problem?.field && coded ? coded : message
            setError(field as FieldName, { message: text || t('operatorForm:invalid_value') })
            shown += 1
          }
        }
        if (shown > 0) setSummaryRequested((n) => n + 1)
        else toast.error(coded || problem?.detail || t('operatorForm:toast.save_error'))
      } else {
        toast.error(t('common:network_error'))
      }
    }
  }

  const summaryItems: SummaryItem[] = FIELD_ORDER.filter((name) => errors[name]?.message).map((name) => ({
    id: name,
    label: label(name),
    message: String(errorText(name)),
  }))

  /** Атрибуты доступности поля: обязательность, ошибка, подсказка. */
  function a11y(name: FieldName, opts: { required?: boolean; hint?: boolean; error?: string; extra?: string } = {}) {
    const error = opts.error ?? errorText(name)
    const ids = [describedBy(name, opts.hint ? 'hint' : undefined, error), opts.extra].filter(Boolean)
    return {
      id: name,
      'aria-required': opts.required ? ('true' as const) : undefined,
      'aria-invalid': errors[name] ? true : undefined,
      'aria-describedby': ids.length ? ids.join(' ') : undefined,
      className: fieldClass(Boolean(errors[name])),
    }
  }

  function text(name: FieldName, opts: { required?: boolean; hint?: string; wide?: boolean; inputMode?: 'numeric' } = {}) {
    return (
      <Field id={name} label={label(name)} required={opts.required} hint={opts.hint} wide={opts.wide} error={errorText(name)}>
        <input inputMode={opts.inputMode} {...a11y(name, { required: opts.required, hint: Boolean(opts.hint) })} {...register(name)} />
      </Field>
    )
  }

  function dateField(name: FieldName, required = true) {
    return (
      <Field id={name} label={label(name)} required={required} error={errorText(name)}>
        <input type="date" {...a11y(name, { required })} {...register(name)} />
      </Field>
    )
  }

  function select(name: FieldName, rows: DirectoryRow[] | undefined, opts: { required?: boolean; hint?: string; placeholder: string }) {
    return (
      <Field id={name} label={label(name)} required={opts.required} hint={opts.hint} error={errorText(name)}>
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

  const iinFieldError = submitCount > 0 ? iinError : undefined

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
          {t('operatorForm:intro')}{' '}
          {t('operatorForm:required_note', { mark: '*' })}
        </p>
      )}
      {readOnly && (
        <div role="alert" className="rounded-lg bg-info-bg p-4 text-info">
          <p className="font-semibold">{t('operatorForm:readonly_title')}</p>
          <p className="mt-1 text-sm leading-5">{t('operatorForm:readonly_text')}</p>
        </div>
      )}
      {dirsError && (
        <p role="alert" className="rounded-lg bg-warning-bg p-4 text-sm leading-5 font-semibold text-warning">
          {t('operatorForm:dirs_error')}
        </p>
      )}

      <fieldset disabled={readOnly} className="m-0 space-y-4 border-0 p-0">
        <FormSection title={t('operatorForm:section.main')}>
          {text('surname', { required: true })}
          {text('firstname', { required: true })}
          {text('patronymic', { hint: t('operatorForm:hint.if_any') })}
          {text('transcription', { required: true, hint: t('operatorForm:hint.transcription') })}
          {dateField('birthDate')}
          {select('sexId', dirs?.sexes, { required: true, placeholder: t('operatorForm:placeholder.choose') })}
          {text('post', { required: true, wide: true })}
        </FormSection>

        <FormSection title={t('operatorForm:section.citizenship')} description={t('operatorForm:section.citizenship_desc')}>
          {select('countryId', dirs?.countries, { required: true, placeholder: t('operatorForm:placeholder.country') })}
          {isResident ? (
            <Field
              id="iin"
              label={label('iin')}
              required
              hint={iinLooksValid ? undefined : t('operatorForm:hint.iin')}
              error={iinFieldError}
            >
              <input
                inputMode="numeric"
                maxLength={12}
                {...a11y('iin', { required: true, hint: !iinLooksValid, error: iinFieldError, extra: 'iin-live' })}
                {...register('iin')}
              />
              {/* fe-2.7: итог проверки ИИН — один анонс после паузы в наборе. */}
              <p
                id="iin-live"
                data-testid="iin-live"
                role="status"
                aria-live="polite"
                className={`mt-1 text-sm leading-5 font-semibold ${iinLooksValid ? 'text-success' : 'text-danger'}`}
              >
                {iinLive}
              </p>
            </Field>
          ) : (
            select('stickId', dirs?.categories, { required: true, placeholder: t('operatorForm:placeholder.category') })
          )}
        </FormSection>

        <FormSection title={t('operatorForm:section.document')}>
          {select('docTypeId', dirs?.document_types, { required: true, placeholder: t('operatorForm:placeholder.doc_type') })}
          {text('docSeries', { hint: t('operatorForm:hint.if_any') })}
          {text('docNumber', { required: true })}
          {text('docIssue', { hint: t('operatorForm:hint.docIssue') })}
          {dateField('docBegin')}
          {dateField('docEnd')}
        </FormSection>

        <FormSection title={t('operatorForm:section.request')}>
          <Field
            id="request"
            label={label('request')}
            required={!isEdit}
            wide
            hint={isEdit ? t('operatorForm:hint.request_edit') : t('operatorForm:hint.request_add')}
            error={errorText('request')}
          >
            {/* FE-1: выбор из RBAC-scoped списка. P2-6: в правке поле заблокировано. */}
            <select
              disabled={isEdit || readOnly}
              aria-readonly={isEdit || undefined}
              {...a11y('request', { required: !isEdit, hint: true })}
              {...register('request')}
            >
              <option value="">{t('operatorForm:placeholder.request')}</option>
              {requestOptions.map((r) => (
                <option key={r.id} value={String(r.id)}>
                  {r.name} — {r.event_name}
                </option>
              ))}
              {currentRequest && !currentRequestInList && (
                <option value={String(currentRequest)}>{t('operatorForm:option.request_fallback', { id: currentRequest })}</option>
              )}
            </select>
          </Field>
          {text('visitObjects', { required: true, wide: true, hint: t('operatorForm:hint.visitObjects') })}
        </FormSection>

        <FormSection title={t('operatorForm:section.files')} description={t('operatorForm:section.files_desc')}>
          {/* Story 5.3 — физически разделённые зоны фото/документа с превью. */}
          <PhotoUpload
            file={photo ?? null}
            existingUrl={initialPhotoUrl}
            onFileChange={(f) => setValue('photo', f ?? undefined, { shouldValidate: true })}
            error={errorText('photo')}
          />
          <DocumentUpload
            file={docScan ?? null}
            existingUrl={initialDocScanUrl}
            onFileChange={(f) => setValue('docScan', f ?? undefined, { shouldValidate: true })}
            error={errorText('docScan')}
          />
        </FormSection>

        {!readOnly && (
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button variant="primary" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t('operatorForm:saving') : isEdit ? t('operatorForm:submit_edit') : t('operatorForm:submit')}
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
  const { t } = useTranslation()
  const known = rows?.some((r) => r.code === current)
  return (
    <select {...attrs} {...registration}>
      <option value="">{rows ? placeholder : t('operatorForm:option.loading')}</option>
      {rows?.map((r) => (
        <option key={r.code} value={r.code}>
          {r.name}
        </option>
      ))}
      {current && !known && <option value={current}>{t('operatorForm:option.unknown_code', { code: current })}</option>}
    </select>
  )
}
