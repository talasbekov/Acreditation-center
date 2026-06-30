import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  approveReviewQueueItem,
  getReviewQueueItem,
  returnReviewQueueItem,
} from '@/api/reviewQueue'
import { ApiError } from '@/api/client'
import { mapApiError } from '@/errors/mapApiError'
import { redirectToLogin } from '@/lib/auth'
import { useRole } from '@/hooks/useRole'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { ReturnReasonDialog } from '@/components/ReturnReasonDialog'

// Роли с настоящим breadcrumb (ходят по scope). Источник — сервер/сессия (useRole),
// НЕ URL: навигация = контур безопасности (оператор не получает псевдо-крошек).
const ADMIN_ROLES = new Set(['superuser', 'superoperator'])

// fe-3.5 — окно «Отменить» для оптимистично-отложенного возврата (Q1 default).
const UNDO_MS = 3000

/** Локализованный ключ ошибки detail-загрузки (паттерн EditAttendeePage). */
function detailErrorKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return 'common:attendee.not_found'
    if (error.status === 403) return 'reviewQueue:no_access'
    if (error.status === 401) return 'common:attendee.session_expired'
  }
  return 'common:attendee.load_error'
}

/** ДД.ММ.ГГГГ (как validators/iin.py `_format_date`) — детерминированно, без ICU. */
function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  return m ? `${m[3]}.${m[2]}.${m[1]}` : iso
}

function flagLabel(t: (k: string) => string, flag: string): string {
  return t(`reviewQueue:flag_${flag}`)
}

/**
 * Story fe-3.3 — Заявка-детали (ApplicationDetailPage, `/queue/:id`). Read-only экран
 * review: фото 3×4 + скан документа (явный placeholder при отсутствии), поля, маск-ИИН,
 * статус-бейдж, подсветка проблем с конкретной причиной, history возвратов (условно).
 * Role-aware навигация (admin breadcrumb / оператор — статичный контекст). Футер
 * «Одобрить»/«Вернуть» — handoff в fe-3.4/fe-3.5 (мутации НЕ здесь). Источник данных —
 * masked review-queue endpoint (не `attendees/{id}` — там сырой ИИН).
 */
export function ApplicationDetailPage() {
  const { t, i18n } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const numericId = Number(id)
  // Валидируем СЫРУЮ строку (как EditAttendeePage): `Number('1e3')`=1000 / `'1.5'`
  // молча загрузили бы не ту запись. `^\d+$` отсекает экспоненту/дробь/мусор; `>0` — ноль.
  // P5 (review): `Number.isSafeInteger` отсекает ≥16-значные id — иначе потеря точности
  // (`Number('99999999999999999999')`=1e20) запросила бы ЧУЖОЙ PK при валидной с виду строке.
  const valid = /^\d+$/.test(id ?? '') && numericId > 0 && Number.isSafeInteger(numericId)

  const role = useRole()
  const isAdmin = role !== undefined && ADMIN_ROLES.has(role)
  // Seam fe-3.5: queue ссылается на `/queue/:id?action=return`. Здесь — только маркер
  // (подсветка кнопки «Вернуть»); диалог/мутация возврата — fe-3.5.
  const returnIntent = searchParams.get('action') === 'return'

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['review-queue-detail', numericId],
    queryFn: () => getReviewQueueItem(numericId),
    enabled: valid,
    retry: false,
  })

  // 401 (истёкшая сессия) → на вход (как RequireAuth), а не «общая ошибка».
  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) redirectToLogin()
  }, [error])

  // P1 (review): сетевая/серверная ошибка (НЕ ожидаемые 401/403/404) → toast + retry.
  // 401→login, 403/404 — содержательные inline-состояния (не сеть): без toast/повтора.
  const isRetryable =
    isError && !(error instanceof ApiError && [401, 403, 404].includes(error.status))
  useEffect(() => {
    if (isRetryable) toast.error(t('common:network_error'))
  }, [isRetryable, t])

  // fe-3.4 — решение «Одобрить» (in_review → ready). Заявка покидает очередь →
  // инвалидируем список + деталь и уводим назад в /queue (реш. Q2). 409/ошибка →
  // toast через FE-маппер fe-1.2 (машинный код, не «сеть»).
  const approveMutation = useMutation({
    mutationFn: () => approveReviewQueueItem(numericId),
    onSuccess: () => {
      toast.success(t('reviewQueue:approve_toast_success'))
      void queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      void queryClient.invalidateQueries({ queryKey: ['review-queue-detail', numericId] })
      navigate('/queue')
    },
    onError: (e) => {
      if (e instanceof ApiError) {
        toast.error(mapApiError(e.problem, t, i18n))
      } else {
        toast.error(t('common:network_error'))
      }
    },
  })

  // fe-3.5 — возврат с причиной. Q1 default: оптимистично-отложенный POST — реальный /return/
  // откладывается на UNDO_MS, «Отменить» отменяет до вызова (нет компенсирующего перехода/
  // двойного аудита). Возврат легален только из in_review (как approve-gate fe-3.4 P1).
  const [returnOpen, setReturnOpen] = useState(false)
  const [returnPending, setReturnPending] = useState(false)
  const returnTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const returnMutation = useMutation({
    mutationFn: (reason: string) => returnReviewQueueItem(numericId, reason),
    onSuccess: () => {
      // toast (с «Отменить») уже показан в confirmReturn при планировании — не дублируем.
      void queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      void queryClient.invalidateQueries({ queryKey: ['review-queue-detail', numericId] })
      navigate('/queue')
    },
    onError: (e) => {
      setReturnPending(false)
      if (e instanceof ApiError) toast.error(mapApiError(e.problem, t, i18n))
      else toast.error(t('common:network_error'))
    },
  })

  // review-урок fe-3.4 P3 — чистим отложенный undo-таймер при unmount.
  useEffect(
    () => () => {
      if (returnTimerRef.current) clearTimeout(returnTimerRef.current)
    },
    [],
  )

  // Seam fe-3.3: вход по ?action=return → авто-открытие диалога (когда данные загружены, in_review).
  useEffect(() => {
    if (returnIntent && data && data.status === 'in_review') setReturnOpen(true)
  }, [returnIntent, data])

  function confirmReturn(reason: string) {
    // Оптимистично-отложенный POST: окно «Отменить» ~UNDO_MS, реальный вызов по таймеру.
    setReturnOpen(false)
    setReturnPending(true)
    const timer = setTimeout(() => {
      returnTimerRef.current = undefined
      returnMutation.mutate(reason)
    }, UNDO_MS)
    returnTimerRef.current = timer
    toast.success(t('reviewQueue:return_toast_success'), {
      duration: UNDO_MS,
      action: {
        label: t('reviewQueue:undo'),
        onClick: () => {
          clearTimeout(timer)
          returnTimerRef.current = undefined
          setReturnPending(false)
        },
      },
    })
  }

  const flags = new Set(data?.problem_flags ?? [])
  const photoFlagged = flags.has('no_photo') || flags.has('photo_ratio')
  const docFlagged = flags.has('doc_unreadable')

  return (
    <div className="mx-auto max-w-4xl p-6">
      <header className="mb-6 border-b border-border pb-4">
        {isAdmin ? (
          <nav aria-label={t('reviewQueue:detail_breadcrumb_aria')} className="mb-2 text-sm">
            <Link
              to="/queue"
              className="rounded text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {t('reviewQueue:title')}
            </Link>
            <span aria-hidden="true" className="mx-1.5 text-text-muted">
              /
            </span>
            <span aria-current="page" className="text-text-muted">
              {t('reviewQueue:detail_crumb_current', { id: numericId })}
            </span>
          </nav>
        ) : data ? (
          // Оператор: статичный нефокусируемый контекст (НЕ псевдо-крошка — изоляция).
          <p className="mb-2 text-sm text-text-muted">
            {t('reviewQueue:detail_context_static', { name: data.full_name })}
          </p>
        ) : null}

        <div className="flex items-start justify-between gap-4">
          <h1 className="text-[15px] font-[650] tracking-[-0.01em] text-text">
            {data ? data.full_name : t('reviewQueue:detail_heading_generic')}
          </h1>
          {data && <StatusBadge status={data.status} />}
        </div>
      </header>

      {!valid && <p className="text-status-rejected">{t('common:attendee.invalid_id')}</p>}
      {/* P2 (review): скелет вместо текста — структура совпадает с загруженной (без layout-shift). */}
      {valid && isPending && <DetailSkeleton />}
      {valid && isError && (
        <div role="alert" className="space-y-3">
          <p className="text-status-rejected">{t(detailErrorKey(error))}</p>
          {/* P1 (review): retry — только для сетевой/серверной ошибки (не 401/403/404). */}
          {isRetryable && (
            <Button variant="outline" type="button" onClick={() => refetch()}>
              {t('common:retry')}
            </Button>
          )}
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-[280px_1fr]">
            <div className="space-y-4">
              <MediaFrame
                url={data.photo}
                label={t('reviewQueue:detail_photo_label')}
                alt={t('reviewQueue:detail_photo_alt')}
                missing={t('reviewQueue:detail_photo_missing')}
                flagged={photoFlagged}
              />
              <MediaFrame
                url={data.doc_scan}
                label={t('reviewQueue:detail_doc_label')}
                alt={t('reviewQueue:detail_doc_alt')}
                missing={t('reviewQueue:detail_doc_missing')}
                flagged={docFlagged}
              />
            </div>

            <div className="space-y-4">
              {data.problem_flags.length > 0 && <ProblemList flags={data.problem_flags} />}

              <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
                <Field label={t('reviewQueue:detail_field_iin')}>
                  <span aria-hidden="true" className="tabular-nums">
                    {data.iin_masked || '—'}
                  </span>
                  {data.iin_masked && (
                    <span className="sr-only">
                      {t('reviewQueue:detail_iin_sr', { last4: data.iin_masked.slice(-4) })}
                    </span>
                  )}
                </Field>
                <Field label={t('reviewQueue:detail_field_birth_date')}>
                  {/* P4 (review): tabular-nums — выравнивание цифр даты (как у ИИН). */}
                  <span className="tabular-nums">{formatDate(data.birth_date)}</span>
                </Field>
                <Field label={t('reviewQueue:detail_field_residency')}>
                  {data.is_resident
                    ? t('reviewQueue:detail_residency_resident')
                    : t('reviewQueue:detail_residency_nonresident')}
                </Field>
                <Field label={t('reviewQueue:detail_field_country')}>{data.country || '—'}</Field>
                <Field label={t('reviewQueue:detail_field_post')}>{data.post || '—'}</Field>
                <Field label={t('reviewQueue:detail_field_transcription')}>
                  {/* Транслитерация НЕ локализуется → lang="en" (SR-произношение, WCAG 3.1.2). */}
                  <span lang="en">{data.transcription || '—'}</span>
                </Field>
                {/* P9 (review, Erda): «Тип документа» из мокапа — хранимый код docTypeId
                    как есть (справочника типов нет → без резолюции в лейбл). */}
                <Field label={t('reviewQueue:detail_field_doc_type')}>{data.doc_type || '—'}</Field>
                <Field label={t('reviewQueue:detail_field_sub_event')}>
                  {data.sub_event_name ?? '—'}
                </Field>
                <Field label={t('reviewQueue:detail_field_created')}>
                  {/* P4 (review): tabular-nums — выравнивание цифр даты. */}
                  <span className="tabular-nums">{formatDate(data.created_at)}</span>
                </Field>
              </dl>

              {/* История возвратов — условно (return_count>0). Источник придёт из 3.5/3.6/3.7. */}
              {data.return_count > 0 && (
                <div className="rounded-md border border-border bg-surface-muted p-3 text-sm">
                  <p className="text-text">
                    {t('reviewQueue:detail_return_history', { count: data.return_count })}
                  </p>
                  {data.last_return_reason && (
                    <p className="mt-1 text-text-muted">
                      {t('reviewQueue:detail_last_reason', { reason: data.last_return_reason })}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Футер решения — стабильные триггеры; мутации/диалог → fe-3.4 / fe-3.5. */}
          <footer className="mt-8 flex items-center justify-between border-t border-border pt-4">
            <span className="text-sm text-text-muted">{t('reviewQueue:detail_decision_label')}</span>
            <div className="flex gap-3">
              <Button
                variant="outline"
                type="button"
                // fe-3.5 — открывает ReturnReasonDialog. Возврат только из in_review (FSM
                // submitted→submitted=409; как approve-gate fe-3.4 P1).
                disabled={returnPending || data.status !== 'in_review'}
                title={
                  data.status !== 'in_review'
                    ? t('reviewQueue:detail_action_pending_hint')
                    : undefined
                }
                onClick={() => setReturnOpen(true)}
                data-testid="action-return"
                className={returnIntent ? 'ring-2 ring-primary ring-offset-2' : undefined}
              >
                {t('reviewQueue:detail_action_return')}
              </Button>
              <Button
                variant="default"
                type="button"
                // review P1 — одобрять можно только in_review (submitted→ready запрещён FSM →
                // 409). Для прочих статусов кнопка disabled с подсказкой, а не падающее действие.
                disabled={approveMutation.isPending || data.status !== 'in_review'}
                title={data.status !== 'in_review' ? t('reviewQueue:detail_action_pending_hint') : undefined}
                onClick={() => approveMutation.mutate()}
                data-testid="action-approve"
              >
                {t('reviewQueue:detail_action_approve')}
              </Button>
            </div>
          </footer>
        </>
      )}

      <ReturnReasonDialog
        open={returnOpen}
        onClose={() => setReturnOpen(false)}
        onSubmit={confirmReturn}
      />
    </div>
  )
}

/** Read-only медиа-рамка 3×4 с явным placeholder (НЕ битый `<img>`) + onError-fallback. */
function MediaFrame({
  url,
  label,
  alt,
  missing,
  flagged,
}: {
  url: string | null
  label: string
  alt: string
  missing: string
  flagged: boolean
}) {
  const [errored, setErrored] = useState(false)
  // P3 (review): сбрасываем флаг ошибки при смене url — иначе после refetch
  // (refetchOnWindowFocus вкл.) или будущей detail→detail навигации (fe-3.4/3.5)
  // ПРИСУТСТВУЮЩЕЕ фото/скан осталось бы плейсхолдером → ревьюер введён в заблуждение.
  useEffect(() => {
    setErrored(false)
  }, [url])
  const ring = flagged ? ' ring-2 ring-status-rejected' : ''
  return (
    <figure className="space-y-1">
      <figcaption className="text-[11px] font-semibold uppercase tracking-[0.04em] text-text-muted">
        {label}
      </figcaption>
      {url && !errored ? (
        <img
          src={url}
          alt={alt}
          onError={() => setErrored(true)}
          className={
            'aspect-[3/4] w-full rounded-md border border-border bg-surface-muted object-contain' +
            ring
          }
        />
      ) : (
        <div
          role="img"
          aria-label={missing}
          className={
            'flex aspect-[3/4] w-full flex-col items-center justify-center gap-2 rounded-md border border-dashed border-input-border bg-surface-muted text-text-muted' +
            ring
          }
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-8 w-8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="m3 16 5-5 4 4 3-3 6 6" />
          </svg>
          <span className="px-2 text-center text-xs">{missing}</span>
        </div>
      )}
    </figure>
  )
}

/** Подсветка проблем: tint + левая полоса + иконка + КОНКРЕТНАЯ локализованная причина. */
function ProblemList({ flags }: { flags: string[] }) {
  const { t } = useTranslation()
  return (
    <ul aria-label={t('reviewQueue:detail_problems_title')} className="space-y-1.5">
      {flags.map((f) => (
        <li
          key={f}
          className="flex items-center gap-2 rounded-md border-l-[3px] border-status-rejected bg-status-rejected-tint px-3 py-2 text-sm text-status-rejected"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-4 w-4 shrink-0"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
          </svg>
          <span>{flagLabel(t, f)}</span>
        </li>
      ))}
    </ul>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-[0.04em] text-text-muted">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm text-text">{children}</dd>
    </div>
  )
}

/** P2 (review) — скелет загрузки: повторяет grid загруженного экрана (две медиа-рамки
 *  3×4 + поля) → подмена на данные без layout-shift (AC-10). */
function DetailSkeleton() {
  const { t } = useTranslation()
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={t('reviewQueue:detail_loading')}
      className="grid grid-cols-1 gap-6 md:grid-cols-[280px_1fr]"
    >
      <div className="space-y-4">
        <div className="aspect-[3/4] w-full animate-pulse rounded-md bg-surface-muted" />
        <div className="aspect-[3/4] w-full animate-pulse rounded-md bg-surface-muted" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded-md bg-surface-muted" />
        ))}
      </div>
    </div>
  )
}
