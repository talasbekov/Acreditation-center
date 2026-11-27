import { useEffect, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { getAttendee, submitAttendee } from '@/api/attendees'
import { ApiError } from '@/api/client'
import { redirectToLogin } from '@/lib/auth'
import { isOperatorEditable } from '@/lib/attendeeStatus'
import { AttendeeForm } from '@/components/AttendeeForm'
import { BackToRegistry, CancelLink } from '@/components/BackToRegistry'
import { PageHeader } from '@/components/ui/form'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Button } from '@/components/ui/button'
import type { AttendeeDetail } from '@/types/attendee'

// P2-2: различаем ошибки detail-загрузки вместо одного общего сообщения.
function detailErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return t('common:attendee.not_found')
    if (error.status === 403) return t('common:attendee.no_access')
    if (error.status === 401) return t('common:attendee.session_expired')
  }
  return t('common:attendee.load_error')
}

function submitErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError) {
    // 400 — сервер перечисляет, чего не хватает (список карточки — текстом сервера);
    // 409 — участник уже не черновик: код ошибки переводится каталогом `errors`.
    const text = error.problem?.detail ?? error.message
    if (error.status === 409 && error.problem?.type) {
      return t(`errors:${error.problem.type}`, { defaultValue: text.replace(/^status:\s*/, '') })
    }
    if (error.status === 400 || error.status === 409) {
      return text.replace(/^status:\s*/, '')
    }
    return text
  }
  return t('common:network_error')
}

/** Статус участника, причина возврата и отправка черновика на проверку (этап C). */
function StatusPanel({ attendee }: { attendee: AttendeeDetail }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const returned = attendee.status === 'draft' && Boolean(attendee.review_comment)
  const submit = useMutation({
    mutationFn: () => submitAttendee(attendee.id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['attendee', attendee.id], updated)
      void queryClient.invalidateQueries({ queryKey: ['attendees'] })
      toast.success(t('operatorForm:toast.submitted'))
    },
  })

  return (
    <section aria-label={t('operatorForm:card.aria')} className="mb-4 space-y-3 rounded-lg border border-line bg-surface p-4 md:p-6">
      <p className="flex flex-wrap items-center gap-2 text-ink">
        <span className="text-ink-2">{t('operatorForm:card.status')}</span>
        <StatusBadge status={attendee.status} returned={returned} />
      </p>
      {returned && (
        <div role="note" className="rounded-lg bg-danger-bg p-3 text-danger">
          <b>{t('operatorForm:card.reason')}</b> {attendee.review_comment}
        </div>
      )}
      {isOperatorEditable(attendee.status) && (
        <div className="space-y-2">
          <p className="text-sm leading-5 text-ink-2">{t('operatorForm:card.submit_note')}</p>
          <Button variant="primary" type="button" disabled={submit.isPending} onClick={() => submit.mutate()}>
            {submit.isPending ? t('operatorForm:card.submitting') : t('operatorForm:card.submit')}
          </Button>
          {submit.isError && (
            <p role="alert" className="rounded-lg bg-danger-bg p-3 text-sm leading-5 font-semibold text-danger">
              {submitErrorMessage(submit.error, t)}
            </p>
          )}
        </div>
      )}
    </section>
  )
}

/** Страница участника (Story 5.5, этап C). Предзаполняет AttendeeForm;
 *  оператор правит только черновик, остальные статусы — только просмотр. */
export function EditAttendeePage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const attendeeId = Number(id)
  // Валидируем СЫРУЮ строку как чистые цифры: `Number('1e3')`=1000 и `Number('1.5')`
  // прошли бы isFinite/isInteger и молча загрузили бы не ту запись. `^\d+$` отсекает
  // экспоненту/дробь/мусор; `>0` отсекает `0`.
  const valid = /^\d+$/.test(id ?? '') && attendeeId > 0

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['attendee', attendeeId],
    queryFn: () => getAttendee(attendeeId),
    enabled: valid,
  })

  // P2-2: 401 (истёкшая сессия) → на вход (как RequireAuth), а не «общая ошибка».
  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) redirectToLogin()
  }, [error])

  const name = data ? [data.surname, data.firstname, data.patronymic].filter(Boolean).join(' ') : ''

  return (
    <div data-ds className="bg-section text-ink">
      <div className="mx-auto max-w-3xl px-4 py-6 md:px-8 md:py-8">
        <BackToRegistry />
        <PageHeader
          title={name || t('operatorForm:page.edit_title')}
          context={name ? t('operatorForm:page.edit_context') : undefined}
        />
        {!valid && <Notice>{t('common:attendee.invalid_id')}</Notice>}
        {valid && isPending && (
          <p role="status" className="text-ink-2">
            {t('common:loading')}
          </p>
        )}
        {valid && isError && <Notice>{detailErrorMessage(error, t)}</Notice>}
        {data && <StatusPanel attendee={data} />}
        {data && (
          <AttendeeForm
            // Новый статус после отправки — форма пересоздаётся и блокируется.
            key={data.status}
            attendeeId={data.id}
            readOnly={!isOperatorEditable(data.status)}
            initialPhotoUrl={data.photo}
            initialDocScanUrl={data.docScan}
            cancel={<CancelLink />}
            initialValues={{
              surname: data.surname,
              firstname: data.firstname,
              patronymic: data.patronymic ?? '',
              birthDate: data.birthDate ?? '',
              countryId: data.countryId,
              iin: data.iin ?? '',
              request: String(data.request),
              transcription: data.transcription ?? '',
              sexId: data.sexId ?? '',
              post: data.post ?? '',
              stickId: data.stickId ?? '',
              docTypeId: data.docTypeId ?? '',
              docSeries: data.docSeries ?? '',
              docNumber: data.docNumber ?? '',
              docBegin: data.docBegin ?? '',
              docEnd: data.docEnd ?? '',
              docIssue: data.docIssue ?? '',
              visitObjects: data.visitObjects ?? '',
            }}
          />
        )}
      </div>
    </div>
  )
}

/** Ошибка загрузки карточки. */
function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-lg bg-danger-bg p-4 font-semibold text-danger">
      {children}
    </p>
  )
}
