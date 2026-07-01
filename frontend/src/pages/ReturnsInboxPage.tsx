import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getAttendees, type AttendeeListParams } from '@/api/attendees'
import { Button } from '@/components/ui/button'

const PAGE_SIZE = 50

function formatReason(reason: string | null): string {
  return reason && reason.trim() ? reason : '—'
}

/**
 * Story fe-3.7 — инбокс возвратов оператора (read-only + edit-link, Q2).
 * Фильтр `returned=true` (submitted + return_count>0, «Возвращена»); строка → EditAttendeePage
 * (правка держит заявку в очереди админа с return-историей). Scope наследован (sub-event, Q1).
 * Масктрованный ИИН (masked-инвариант). Реюз паттерна AttendeesPage + StatusBadge; DESIGN-токены.
 */
export function ReturnsInboxPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)

  const params: AttendeeListParams = { page, page_size: PAGE_SIZE, returned: true }
  const { data, isPending, isError, isPlaceholderData } = useQuery({
    queryKey: ['returns-inbox', { page }],
    queryFn: () => getAttendees(params),
    placeholderData: keepPreviousData,
  })

  const total = data?.count ?? 0
  const from = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const to = Math.min(page * PAGE_SIZE, total)

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="mb-4 text-[15px] font-[650] tracking-[-0.01em] text-text">
        {t('reviewQueue:inbox_title')}
      </h1>

      {/* review P4 — error/pending/empty/table взаимоисключающи: на isError НЕ рендерим
          фантомную пустую таблицу + «показано 0 из 0» под сообщением ошибки. */}
      {isError ? (
        <p className="text-status-rejected">{t('reviewQueue:inbox_load_error')}</p>
      ) : isPending ? (
        <SkeletonTable />
      ) : !data || data.results.length === 0 ? (
        <p className="py-12 text-center text-text-muted">{t('reviewQueue:inbox_empty')}</p>
      ) : (
        <>
          <table className="w-full border-collapse text-base">
            <thead>
              <tr className="border-b border-border text-left text-text-muted">
                <th scope="col" className="py-2 pr-3">{t('reviewQueue:inbox_col_name')}</th>
                <th scope="col" className="py-2 pr-3">{t('reviewQueue:inbox_col_iin')}</th>
                <th scope="col" className="py-2 pr-3">{t('reviewQueue:inbox_col_status')}</th>
                <th scope="col" className="py-2 pr-3">{t('reviewQueue:inbox_col_reason')}</th>
                <th scope="col" className="py-2 pr-3">{t('reviewQueue:inbox_col_count')}</th>
                <th scope="col" className="py-2">{t('reviewQueue:inbox_col_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {data?.results.map((a) => (
                <tr
                  key={a.id}
                  className="cursor-pointer border-b border-border hover:bg-surface-muted"
                  onClick={() => navigate(`/attendees/${a.id}`)}
                >
                  <td className="py-2 pr-3 text-text">
                    {[a.surname, a.firstname, a.patronymic].filter(Boolean).join(' ')}
                  </td>
                  <td className="py-2 pr-3 text-text">{a.iin_masked || '—'}</td>
                  <td className="py-2 pr-3">
                    {/* review P3 (AC-3): «Возвращена»-аффорданс через reserved status-rejected
                        (все строки инбокса — возвраты; отличает от обычного submitted). */}
                    <span className="inline-flex items-center rounded-full border border-status-rejected px-2 py-0.5 text-xs font-medium text-status-rejected">
                      {t('reviewQueue:inbox_returned_label')}
                    </span>
                  </td>
                  <td className="max-w-xs truncate py-2 pr-3 text-text-muted" title={a.last_return_reason ?? undefined}>
                    {formatReason(a.last_return_reason)}
                  </td>
                  <td className="py-2 pr-3 tabular-nums text-text">{a.return_count}</td>
                  <td className="py-2">
                    <Button
                      variant="outline"
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/attendees/${a.id}`)
                      }}
                    >
                      {t('reviewQueue:inbox_action_fix')}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mt-4 flex items-center justify-between">
            <span className="text-sm text-text-muted">
              {t('common:pagination.showing', { from, to, total })}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                type="button"
                disabled={isPlaceholderData || !data?.previous}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                {t('common:actions.prev')}
              </Button>
              <Button
                variant="outline"
                type="button"
                disabled={isPlaceholderData || !data?.next}
                onClick={() => setPage((p) => p + 1)}
              >
                {t('common:actions.next')}
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function SkeletonTable() {
  const { t } = useTranslation()
  return (
    <div aria-label={t('reviewQueue:inbox_loading')} className="space-y-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-md bg-surface-muted" />
      ))}
    </div>
  )
}
