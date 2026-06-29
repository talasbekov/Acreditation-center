import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { getAttendee } from '@/api/attendees'
import { ApiError } from '@/api/client'
import { redirectToLogin } from '@/lib/auth'
import { AttendeeForm } from '@/components/AttendeeForm'

// Статусы, после которых редактирование заблокировано (сервер тоже отдаёт 403).
const LOCKED_STATUSES = new Set(['ready', 'exported'])

// P2-2: различаем ошибки detail-загрузки вместо одного общего сообщения. fe-1.4:
// возвращаем i18n-ключ (common namespace); статус-маппинг здесь, не серверный код-контракт.
function detailErrorKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return 'common:attendee.not_found'
    if (error.status === 403) return 'common:attendee.no_access'
    if (error.status === 401) return 'common:attendee.session_expired'
  }
  return 'common:attendee.load_error'
}

/** Страница редактирования участника (Story 5.5). Предзаполняет AttendeeForm;
 *  read-only при статусе ready/exported. */
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

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-6 text-2xl font-semibold text-neutral-900">
        {t('operatorForm:page.edit_title')}
      </h1>
      {!valid && <p className="text-red-600">{t('common:attendee.invalid_id')}</p>}
      {valid && isPending && <p className="text-neutral-700">{t('common:loading')}</p>}
      {valid && isError && (
        <p className="text-red-600">{t(detailErrorKey(error))}</p>
      )}
      {data && (
        <AttendeeForm
          attendeeId={data.id}
          readOnly={LOCKED_STATUSES.has(data.status)}
          initialPhotoUrl={data.photo}
          initialDocScanUrl={data.docScan}
          initialValues={{
            surname: data.surname,
            firstname: data.firstname,
            patronymic: data.patronymic ?? '',
            birthDate: data.birthDate ?? '',
            countryId: data.countryId,
            iin: data.iin ?? '',
            request: String(data.request),
          }}
        />
      )}
    </div>
  )
}
