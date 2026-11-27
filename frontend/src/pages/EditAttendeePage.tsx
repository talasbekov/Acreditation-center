import { useEffect, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
function detailErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return 'Участник не найден.'
    if (error.status === 403) return 'Нет доступа к этому участнику.'
    if (error.status === 401) return 'Сессия истекла. Перенаправление на вход…'
  }
  return 'Не удалось загрузить участника.'
}

function submitErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    // 400 — сервер перечисляет, чего не хватает; 409 — участник уже не черновик.
    const text = error.problem?.detail ?? error.message
    if (error.status === 400 || error.status === 409) {
      return text.replace(/^status:\s*/, '')
    }
    return text
  }
  return 'Сеть недоступна. Повторите.'
}

/** Статус участника, причина возврата и отправка черновика на проверку (этап C). */
function StatusPanel({ attendee }: { attendee: AttendeeDetail }) {
  const queryClient = useQueryClient()
  const returned = attendee.status === 'draft' && Boolean(attendee.review_comment)
  const submit = useMutation({
    mutationFn: () => submitAttendee(attendee.id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['attendee', attendee.id], updated)
      void queryClient.invalidateQueries({ queryKey: ['attendees'] })
      toast.success('Участник отправлен на проверку')
    },
  })

  return (
    <section aria-label="Статус участника" className="mb-4 space-y-3 rounded-lg border border-line bg-surface p-4 md:p-6">
      <p className="flex flex-wrap items-center gap-2 text-ink">
        <span className="text-ink-2">Статус:</span>
        <StatusBadge status={attendee.status} returned={returned} />
      </p>
      {returned && (
        <div role="note" className="rounded-lg bg-danger-bg p-3 text-danger">
          <b>Причина возврата:</b> {attendee.review_comment}
        </div>
      )}
      {isOperatorEditable(attendee.status) && (
        <div className="space-y-2">
          <p className="text-sm leading-5 text-ink-2">
            Сначала сохраните изменения: на проверку уходят сохранённые данные. После отправки правка закрыта до решения проверяющего.
          </p>
          <Button variant="primary" type="button" disabled={submit.isPending} onClick={() => submit.mutate()}>
            {submit.isPending ? 'Отправка…' : 'Отправить на проверку'}
          </Button>
          {submit.isError && (
            <p role="alert" className="rounded-lg bg-danger-bg p-3 text-sm leading-5 font-semibold text-danger">
              {submitErrorMessage(submit.error)}
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
    <main data-ds className="min-h-svh bg-section text-ink">
      <div className="mx-auto max-w-3xl px-4 py-6 md:px-8 md:py-8">
        <BackToRegistry />
        <PageHeader title={name || 'Участник'} context={name ? 'Карточка участника' : undefined} />
        {!valid && <Notice>Некорректный идентификатор участника.</Notice>}
        {valid && isPending && (
          <p role="status" className="text-ink-2">
            Загрузка…
          </p>
        )}
        {valid && isError && <Notice>{detailErrorMessage(error)}</Notice>}
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
    </main>
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
