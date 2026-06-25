import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { attendeeSchema, type AttendeeFormValues } from '@/lib/attendeeSchema'
import { KZ_COUNTRY_ID } from '@/lib/constants'
import { apiFetch, ApiError } from '@/api/client'
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
        toast.success('Изменения сохранены')
      } else {
        toast.success('Участник добавлен')
        clearDraft() // AC-4: успех → черновик удаляется (reset→пустая форма не пересоздаёт его)
        setDraftSaved(false)
        reset()
      }
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
    } finally {
      suppressSaveRef.current = false // возобновляем автосейв (на ошибке черновик сохранён)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      {/* Story 5.4 — баннер восстановления черновика */}
      {showRestore && (
        <div role="alert" className="rounded-md border border-amber-400 bg-amber-50 p-3">
          <p className="mb-2 font-medium text-neutral-900">
            Найден несохранённый черновик. Восстановить?
          </p>
          <div className="flex gap-2">
            <Button type="button" onClick={handleRestoreDraft}>
              Да
            </Button>
            <Button type="button" variant="outline" onClick={handleDiscardDraft}>
              Начать заново
            </Button>
          </div>
        </div>
      )}
      {/* Story 5.4 — ненавязчивый индикатор автосохранения (AC-1) */}
      {draftSaved && (
        <p aria-live="polite" className="text-sm text-green-700">
          Черновик сохранён
        </p>
      )}
      {/* Story 5.5 — read-only баннер (статус ready/exported) */}
      {readOnly && (
        <div role="alert" className="rounded-md border border-neutral-400 bg-neutral-100 p-3 text-neutral-900">
          Редактирование заблокировано
        </div>
      )}

      {/* Поля блокируются: пока открыт баннер черновика (5.4) или read-only (5.5). */}
      <fieldset disabled={showRestore || readOnly} className="m-0 space-y-4 border-0 p-0">
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

      <Field label="Категория (мероприятие)" error={errors.request?.message}>
        {/* FE-1: выбор Request из RBAC-scoped списка вместо ручного PK.
            P2-6: в edit поле disabled — оператор не должен «переселять» участника
            в другое событие (сервер тоже ограничивает RBAC, но UI не предлагает). */}
        <select
          id="request"
          disabled={isEdit || readOnly}
          aria-readonly={isEdit || undefined}
          className={`${inputCls} ${isEdit ? 'bg-neutral-100 text-neutral-600' : ''}`}
          {...register('request')}
        >
          <option value="">— выберите категорию —</option>
          {requestOptions.map((r) => (
            <option key={r.id} value={String(r.id)}>
              {r.name} — {r.event_name}
            </option>
          ))}
          {/* Текущее значение (edit/draft) может быть вне загруженного списка —
              fallback-опция, чтобы select не сбрасывал предзаполненный request. */}
          {currentRequest && !currentRequestInList && (
            <option value={String(currentRequest)}>
              Категория #{currentRequest}
            </option>
          )}
        </select>
      </Field>

      {/* Story 5.3 — физически разделённые зоны фото/документа с preview. */}
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

      {!readOnly && (
        <Button type="submit" disabled={isSubmitting}>
          {isEdit ? 'Сохранить изменения' : 'Сохранить'}
        </Button>
      )}
      </fieldset>

      {/* Story 5.4 — постоянная подпись изоляции (только в режиме добавления) */}
      {!isEdit && (
        <p className="text-xs text-neutral-500">
          Черновик сохраняется только в этом браузере
        </p>
      )}
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
