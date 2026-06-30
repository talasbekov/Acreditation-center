import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { attendeeSchema, type AttendeeFormValues } from '@/lib/attendeeSchema'
import { translateFieldError } from '@/lib/validationError'
import { KZ_COUNTRY_ID } from '@/lib/constants'
import { apiFetch, ApiError } from '@/api/client'
import { mapApiError } from '@/errors/mapApiError'
import { getRequests } from '@/api/requests'
import { Button } from '@/components/ui/button'
import { PhotoUpload } from '@/components/PhotoUpload/PhotoUpload'
import { DocumentUpload } from '@/components/DocumentUpload/DocumentUpload'
import {
  clearDraft,
  hasDraft,
  isMeaningfulDraft,
  loadDraft,
  saveDraft,
  type AttendeeDraft,
} from '@/lib/draftStorage'

const SERVER_FIELDS: ReadonlySet<string> = new Set([
  'surname',
  'firstname',
  'patronymic',
  'birthDate',
  'countryId',
  'iin',
  'request',
  'photo',
  'docScan',
])

const DEFAULT_VALUES: AttendeeFormValues = {
  surname: '',
  firstname: '',
  patronymic: '',
  birthDate: '',
  countryId: KZ_COUNTRY_ID,
  iin: '',
  request: '',
  photo: undefined,
  docScan: undefined,
}

const DRAFT_AUTOSAVE_MS = 2000
const DRAFT_INDICATOR_MS = 2500
// fe-2.7 (AC-2): debounce SR-анонса статуса ИИН — при быстром вводе 12 цифр live-регион
// мутирует ровно 1 раз на settle (визуал ✅/границы — мгновенный, не debounce'ится).
const IIN_ANNOUNCE_MS = 500

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
}

/**
 * Форма участника. Add (Story 5.2-5.4): real-time ИИН-валидация, residency switch,
 * multipart submit, автосохранение черновика. Edit (Story 5.5): предзаполнение +
 * PATCH; черновик-автосейв в edit отключён; readOnly блокирует поля.
 */
export function AttendeeForm({
  attendeeId,
  initialValues,
  readOnly = false,
  initialPhotoUrl,
  initialDocScanUrl,
}: AttendeeFormProps = {}) {
  const isEdit = attendeeId !== undefined
  const { t, i18n } = useTranslation()
  // fe-1.4: zod-ошибки приходят как i18n-ключи → переводим в текст поля.
  const fe = (m?: string) => translateFieldError(t, m)
  const queryClient = useQueryClient()
  const {
    register,
    handleSubmit,
    watch,
    reset,
    setError,
    setValue,
    trigger,
    formState: { errors, isSubmitting },
  } = useForm<AttendeeFormValues>({
    resolver: zodResolver(attendeeSchema),
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
  const iinLooksValid = isResident && iin.trim() !== '' && !errors.iin

  // fe-2.7 (AC-1): единая обвязка a11y контрола — обязательность + связка ошибки по id.
  // Гейт по ПЕРЕВЕДЁННОМУ тексту (как у <Field error={fe(...)}>): aria-describedby ставим
  // только когда Field реально отрендерит узел `${name}-error` — иначе ссылка повисла бы
  // на несуществующем узле при пустом/непереводимом message.
  const ariaFor = (name: keyof AttendeeFormValues, required: boolean) => {
    const hasError = !!fe(errors[name]?.message)
    return {
      'aria-required': required || undefined,
      'aria-invalid': hasError ? true : undefined,
      'aria-describedby': hasError ? `${name}-error` : undefined,
    }
  }

  // fe-2.7 (AC-2): целевой текст SR-анонса ИИН — строка (не объект), чтобы эффект ниже
  // зависел от значения и сбрасывал debounce-таймер только на реальном изменении статуса.
  const [iinAnnounce, setIinAnnounce] = useState('')
  const iinAnnounceTarget =
    isResident && iin.trim() !== ''
      ? errors.iin
        ? fe(errors.iin.message) ?? ''
        : t('operatorForm:iin_valid_aria')
      : ''

  // FE-1: RBAC-scoped список Request («категория») для селектора. В edit поле
  // read-only (P2-6) → список не нужен (enabled:false); текущее значение показываем
  // fallback-опцией, чтобы select не терял предзаполненный/draft request.
  const { data: requestOptions = [] } = useQuery({
    queryKey: ['requests'],
    queryFn: getRequests,
    enabled: !isEdit,
    staleTime: 5 * 60_000,
  })
  const currentRequestInList = requestOptions.some(
    (r) => String(r.id) === String(currentRequest),
  )

  // Cross-field: при изменении даты рождения перевалидировать ИИН (RHF по умолчанию
  // ревалидирует только изменённое поле → иначе ошибка несовпадения устаревает).
  useEffect(() => {
    if (isResident && iin.trim() !== '') void trigger('iin')
  }, [birthDate, isResident, iin, trigger])

  // fe-2.7 (AC-2): коммит анонса ИИН с debounce. Таймер сбрасывается на КАЖДОМ изменении iin
  // (а не только при смене текста статуса) → анонс единожды после реальной паузы ввода (на
  // settle), независимо от скорости набора: при медленном вводе промежуточный статус
  // («нужно 12 цифр») больше не «прорывается» в live-регион до завершения ввода.
  useEffect(() => {
    const id = setTimeout(() => setIinAnnounce(iinAnnounceTarget), IIN_ANNOUNCE_MS)
    return () => clearTimeout(id)
  }, [iin, iinAnnounceTarget])

  // ── Story 5.4: автосохранение черновика (localStorage) ─────────────────
  const [showRestore, setShowRestore] = useState(false)
  const [savedDraft, setSavedDraft] = useState<AttendeeDraft | null>(null)
  const [draftSaved, setDraftSaved] = useState(false)
  // Пока баннер восстановления открыт — НЕ автосохранять (иначе debounce затрёт
  // черновик пустой формой до того, как оператор нажал «Да»).
  const suppressSaveRef = useRef(false)
  // Таймер debounce в ref (не в скоупе эффекта) — чтобы submit/discard могли
  // отменить отложенный сейв и он не «воскресил» черновик после clearDraft().
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const indicatorTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  // На mount: есть значимый черновик → показать баннер и приостановить автосейв.
  // Только в режиме ДОБАВЛЕНИЯ (черновик — про add, не про edit).
  useEffect(() => {
    if (!isEdit && hasDraft()) {
      suppressSaveRef.current = true
      setSavedDraft(loadDraft())
      setShowRestore(true)
    }
  }, [isEdit])

  // Debounce 2с: watch(callback) срабатывает только на реальных изменениях полей.
  useEffect(() => {
    const sub = watch((values) => {
      if (isEdit) return // edit-режим — автосейв черновика отключён
      if (suppressSaveRef.current) return
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current) // отменяем предыдущий
      if (!isMeaningfulDraft(values)) return // пустая форма → новый сейв не планируем
      saveTimerRef.current = setTimeout(() => {
        saveDraft(values)
        setDraftSaved(true)
        if (indicatorTimerRef.current) clearTimeout(indicatorTimerRef.current)
        indicatorTimerRef.current = setTimeout(() => setDraftSaved(false), DRAFT_INDICATOR_MS)
      }, DRAFT_AUTOSAVE_MS)
    })
    return () => {
      sub.unsubscribe()
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      if (indicatorTimerRef.current) clearTimeout(indicatorTimerRef.current)
    }
  }, [watch, isEdit])

  function handleRestoreDraft() {
    if (savedDraft) reset({ ...DEFAULT_VALUES, ...savedDraft })
    suppressSaveRef.current = false
    setShowRestore(false)
    void trigger() // ревалидация восстановленных значений — убрать ложную зелёную ✅
  }

  function handleDiscardDraft() {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    clearDraft()
    reset(DEFAULT_VALUES)
    suppressSaveRef.current = false
    setShowRestore(false)
  }

  async function onSubmit(values: AttendeeFormValues) {
    // Story 5.4: на время submit гасим автосейв и отменяем отложенный сейв —
    // иначе pending-таймер мог бы записать черновик уже после clearDraft().
    suppressSaveRef.current = true
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)

    // Story 5.3: multipart (фото/документ — файлы). apiFetch НЕ ставит JSON
    // Content-Type для non-string body → браузер сам выставит multipart boundary.
    const fd = new FormData()
    fd.append('surname', values.surname)
    fd.append('firstname', values.firstname)
    fd.append('patronymic', values.patronymic)
    fd.append('birthDate', values.birthDate)
    fd.append('countryId', values.countryId)
    // request уже провалидирован zod (`^\d+$`) — слать как есть (без лоссового Number).
    fd.append('request', values.request)
    // Нерезидент — ИИН не отправляем (сервер выведет is_resident из countryId).
    fd.append('iin', isResident ? values.iin.trim() : '')
    if (values.photo) fd.append('photo', values.photo)
    if (values.docScan) fd.append('docScan', values.docScan)
    try {
      await apiFetch(
        isEdit ? `/api/v1/attendees/${attendeeId}/` : '/api/v1/attendees/',
        { method: isEdit ? 'PATCH' : 'POST', body: fd },
      )
      // AC-6: обновляем кэш списка участников после мутации.
      void queryClient.invalidateQueries({ queryKey: ['attendees'] })
      if (isEdit) {
        // Edit: инвалидируем и detail-кэш (EditAttendeePage: ['attendee', id]),
        // иначе после сохранения на странице остался бы устаревший detail.
        void queryClient.invalidateQueries({ queryKey: ['attendee', attendeeId] })
        toast.success(t('operatorForm:toast.updated'))
      } else {
        toast.success(t('operatorForm:toast.added'))
        clearDraft() // AC-4: успех → черновик удаляется (reset→пустая форма не пересоздаёт его)
        setDraftSaved(false)
        reset()
      }
    } catch (e) {
      if (e instanceof ApiError) {
        const field = e.problem?.field
        // fe-1.2: текст ошибки — из маппера кодов (t('errors:'+type, params)), не из detail/title.
        const message = mapApiError(e.problem, t, i18n)
        // ИИН-поле скрыто у нерезидента — setError на нём был бы невидим → toast.
        const fieldHidden = field === 'iin' && !isResident
        if (field && SERVER_FIELDS.has(field) && !fieldHidden) {
          setError(field as keyof AttendeeFormValues, { message })
        } else {
          toast.error(message)
        }
      } else {
        toast.error(t('common:network_error'))
      }
    } finally {
      suppressSaveRef.current = false // возобновляем автосейв (на ошибке черновик сохранён)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      {/* Story 5.4 — баннер восстановления черновика */}
      {showRestore && (
        <div role="alert" className="rounded-md border border-status-checking bg-status-checking-tint p-3">
          <p className="mb-2 font-medium text-text">
            {t('operatorForm:draft.restore_prompt')}
          </p>
          <div className="flex gap-2">
            <Button type="button" onClick={handleRestoreDraft}>
              {t('operatorForm:draft.restore')}
            </Button>
            <Button type="button" variant="outline" onClick={handleDiscardDraft}>
              {t('operatorForm:draft.discard')}
            </Button>
          </div>
        </div>
      )}
      {/* Story 5.4 — ненавязчивый индикатор автосохранения (AC-1) */}
      {draftSaved && (
        <p aria-live="polite" className="text-sm text-status-active">
          {t('operatorForm:draft.saved')}
        </p>
      )}
      {/* Story 5.5 — read-only баннер (статус ready/exported) */}
      {readOnly && (
        <div role="alert" className="rounded-md border border-border-strong bg-surface-muted p-3 text-text">
          {t('operatorForm:readonly_banner')}
        </div>
      )}

      {/* Поля блокируются: пока открыт баннер черновика (5.4) или read-only (5.5). */}
      <fieldset disabled={showRestore || readOnly} className="m-0 space-y-4 border-0 p-0">
      <Field label={t('operatorForm:label.surname')} fieldId="surname" required error={fe(errors.surname?.message)}>
        <input id="surname" className={inputCls} {...ariaFor('surname', true)} {...register('surname')} />
      </Field>
      <Field label={t('operatorForm:label.firstname')} fieldId="firstname" required error={fe(errors.firstname?.message)}>
        <input id="firstname" className={inputCls} {...ariaFor('firstname', true)} {...register('firstname')} />
      </Field>
      <Field label={t('operatorForm:label.patronymic')} fieldId="patronymic" error={fe(errors.patronymic?.message)}>
        <input id="patronymic" className={inputCls} {...ariaFor('patronymic', false)} {...register('patronymic')} />
      </Field>
      <Field label={t('operatorForm:label.birth_date')} fieldId="birthDate" required error={fe(errors.birthDate?.message)}>
        <input id="birthDate" type="date" className={inputCls} {...ariaFor('birthDate', true)} {...register('birthDate')} />
      </Field>

      <Field label={t('operatorForm:label.country')} fieldId="countryId" required error={fe(errors.countryId?.message)}>
        <select id="countryId" className={inputCls} {...ariaFor('countryId', true)} {...register('countryId')}>
          <option value={KZ_COUNTRY_ID}>{t('operatorForm:country.resident')}</option>
          <option value="643">{t('operatorForm:country.non_resident')}</option>
        </select>
      </Field>

      {isResident && (
        <>
          <Field
            label={t('operatorForm:label.iin')}
            fieldId="iin"
            required
            suppressErrorLive
            error={fe(errors.iin?.message)}
          >
            <div className="flex items-center gap-2">
              <input
                id="iin"
                inputMode="numeric"
                maxLength={12}
                className={`${inputCls} ${errors.iin ? 'border-status-rejected' : ''}`}
                {...ariaFor('iin', true)}
                {...register('iin')}
              />
              {/* fe-2.7: ✅ декоративна (aria-hidden) — статус озвучивает live-регион ниже,
                  и accessible name поля ИИН не загрязняется (снимает воркэраунд fe-2.6). */}
              {iinLooksValid && (
                <span aria-hidden="true" className="text-status-active text-xl">
                  ✅
                </span>
              )}
            </div>
          </Field>
          {/* fe-2.7 (AC-2): единый polite live-регион ИИН (debounced → мутация=1 на settle).
              suppressErrorLive выше убирает role=alert у видимой ошибки, чтобы не было
              ассертивного спама на каждой цифре. */}
          <p aria-live="polite" className="sr-only" data-testid="iin-live">
            {iinAnnounce}
          </p>
        </>
      )}

      <Field label={t('operatorForm:label.category')} fieldId="request" required error={fe(errors.request?.message)}>
        {/* FE-1: выбор Request из RBAC-scoped списка вместо ручного PK.
            P2-6: в edit поле disabled — оператор не должен «переселять» участника
            в другое событие (сервер тоже ограничивает RBAC, но UI не предлагает). */}
        <select
          id="request"
          disabled={isEdit || readOnly}
          aria-readonly={isEdit || undefined}
          className={`${inputCls} ${isEdit ? 'bg-surface-muted text-text-muted' : ''}`}
          {...ariaFor('request', true)}
          {...register('request')}
        >
          <option value="">{t('operatorForm:category.placeholder')}</option>
          {requestOptions.map((r) => (
            <option key={r.id} value={String(r.id)}>
              {r.name} — {r.event_name}
            </option>
          ))}
          {/* Текущее значение (edit/draft) может быть вне загруженного списка —
              fallback-опция, чтобы select не сбрасывал предзаполненный request. */}
          {currentRequest && !currentRequestInList && (
            <option value={String(currentRequest)}>
              {t('operatorForm:category.fallback_option', { id: currentRequest })}
            </option>
          )}
        </select>
      </Field>

      {/* Story 5.3 — физически разделённые зоны фото/документа с preview. */}
      <PhotoUpload
        file={photo ?? null}
        existingUrl={initialPhotoUrl}
        onFileChange={(f) => setValue('photo', f ?? undefined, { shouldValidate: true })}
        error={fe(errors.photo?.message)}
      />
      <DocumentUpload
        file={docScan ?? null}
        existingUrl={initialDocScanUrl}
        onFileChange={(f) => setValue('docScan', f ?? undefined, { shouldValidate: true })}
        error={fe(errors.docScan?.message)}
      />

      {!readOnly && (
        <Button type="submit" disabled={isSubmitting}>
          {isEdit ? t('operatorForm:submit_edit') : t('operatorForm:submit')}
        </Button>
      )}
      </fieldset>

      {/* Story 5.4 — постоянная подпись изоляции (только в режиме добавления) */}
      {!isEdit && (
        <p className="text-xs text-text-muted">
          {t('operatorForm:draft.isolation_note')}
        </p>
      )}
    </form>
  )
}

const inputCls =
  'w-full rounded-md border border-input-border px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'

function Field({
  label,
  fieldId,
  error,
  required = false,
  suppressErrorLive = false,
  children,
}: {
  label: string
  /** id связанного контрола — из него детерминируется id текста ошибки (`${fieldId}-error`). */
  fieldId: string
  error?: string
  required?: boolean
  /** fe-2.7: ИИН ставит true — анонс ошибки идёт через debounced polite live-регион, не role=alert. */
  suppressErrorLive?: boolean
  children: ReactNode
}) {
  const { t } = useTranslation()
  return (
    <div className="block">
      <span className="mb-1 block text-text">
        {/* htmlFor-ассоциация: <label> содержит ТОЛЬКО текст метки → accessible name контрола
            остаётся чистым ("Фамилия"), а маркеры обязательности — вне <label>. */}
        <label htmlFor={fieldId}>{label}</label>
        {/* fe-2.7 (AC-1): обязательность не только цветом — звёздочка + «(обязательно)».
            aria-hidden: SR узнаёт обязательность из aria-required контрола (без дублей). */}
        {required && (
          <span aria-hidden="true" className="text-status-rejected"> *</span>
        )}
        {required && (
          <span aria-hidden="true" className="ml-1 text-sm font-normal text-text-muted">
            {t('operatorForm:a11y.required_suffix')}
          </span>
        )}
      </span>
      {children}
      {error && (
        <p
          id={`${fieldId}-error`}
          role={suppressErrorLive ? undefined : 'alert'}
          className="mt-1 text-sm text-status-rejected"
        >
          {error}
        </p>
      )}
    </div>
  )
}
