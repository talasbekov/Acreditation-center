import { useEffect, useId, useRef, useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { getAttendees, type AttendeeListParams } from '@/api/attendees'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { STATUS_CODES, isStatusCode } from '@/lib/attendeeStatus'
import { registryState } from '@/lib/registryState'
import { useMediaQuery } from '@/lib/useMediaQuery'
import type { Attendee } from '@/types/attendee'

const PAGE_SIZE = 50
const SEARCH_DEBOUNCE_MS = 300
const SEARCH_MIN_CHARS = 3

const fieldCls =
  'h-11 w-full rounded-md border border-field bg-surface px-3 text-base text-ink placeholder:text-ink-2'

/** Локаль дат по языку интерфейса (ключ kz → ISO kk). */
const DATE_LOCALES: Record<string, string> = { ru: 'ru-RU', kz: 'kk-KZ', en: 'en-GB' }

function formatDate(iso: string, lang: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString(DATE_LOCALES[lang] ?? 'ru-RU')
}

function fullName(a: Attendee): string {
  return [a.surname, a.firstname, a.patronymic].filter(Boolean).join(' ')
}

function requestLine(a: Attendee, t: TFunction): string {
  return [a.request_name ? t('common:attendees.request', { name: a.request_name }) : '', a.event_name ?? '']
    .filter(Boolean)
    .join(' · ')
}

function readPage(value: string | null): number {
  const n = Number(value)
  return Number.isInteger(n) && n > 0 ? n : 1
}

/**
 * Реестр участников — эталон этапа D (desktop-таблица и mobile-карточки).
 * Поиск, статус, страницы — Story 5.5; контекст возврата — `lib/registryState`.
 */
export function AttendeesPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const isDesktop = useMediaQuery('(min-width: 768px)')
  const hintId = useId()
  const filtersId = useId()

  const status = isStatusCode(params.get('status') ?? '') ? (params.get('status') as string) : ''
  const page = readPage(params.get('page'))

  const [searchInput, setSearchInput] = useState(() => registryState.get().search)
  const [search, setSearch] = useState(() => {
    const v = registryState.get().search.trim()
    return v.length >= SEARCH_MIN_CHARS ? v : ''
  })
  const [filtersOpen, setFiltersOpen] = useState(false)
  const searchRef = useRef(search)

  function update(next: { status?: string; page?: number }) {
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev)
        const s = next.status ?? p.get('status') ?? ''
        const pg = next.page ?? readPage(p.get('page'))
        if (s) p.set('status', s)
        else p.delete('status')
        if (pg > 1) p.set('page', String(pg))
        else p.delete('page')
        return p
      },
      { replace: true },
    )
  }

  // Адрес реестра с фильтрами — для «К списку участников» из карточки и формы.
  useEffect(() => {
    registryState.set({ listUrl: location.pathname + location.search })
  }, [location.pathname, location.search])

  // Поиск: debounce 300 мс, запрос от 3 символов. Новая строка поиска — с первой страницы.
  useEffect(() => {
    registryState.set({ search: searchInput })
    const timer = setTimeout(() => {
      const v = searchInput.trim()
      const next = v.length >= SEARCH_MIN_CHARS ? v : ''
      if (next !== searchRef.current) {
        searchRef.current = next
        setSearch(next)
        update({ page: 1 })
      }
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
    // update меняет только адрес; перезапуск нужен лишь при новой строке ввода.
  }, [searchInput])

  const query: AttendeeListParams = { page, page_size: PAGE_SIZE }
  if (search) query.search = search
  if (status) query.status = status

  const { data, isPending, isError, isPlaceholderData, refetch, isFetching } = useQuery({
    queryKey: ['attendees', { search, status, page }],
    queryFn: () => getAttendees(query),
    placeholderData: keepPreviousData, // строки не «прыгают» при смене страницы
  })

  // Возврат из карточки: фокус на строке открытого участника.
  useEffect(() => {
    const id = registryState.get().lastOpenedId
    if (!data || id == null) return
    const el = document.querySelector<HTMLElement>(`[data-open-id="${id}"]`)
    if (el) {
      el.focus()
      el.scrollIntoView?.({ block: 'center' })
    }
    registryState.set({ lastOpenedId: null })
  }, [data, isDesktop])

  function open(id: number) {
    registryState.set({ lastOpenedId: id })
    navigate(`/attendees/${id}`)
  }

  function resetFilters() {
    setSearchInput('')
    searchRef.current = ''
    setSearch('')
    update({ status: '', page: 1 })
  }

  const typed = searchInput.trim().length
  const shortSearch = typed > 0 && typed < SEARCH_MIN_CHARS
  const hasFilters = Boolean(search || status)
  const total = data?.count ?? 0
  const from = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const to = Math.min(page * PAGE_SIZE, total)
  const rows = data?.results ?? []

  const statusSelect = (
    <div className="md:w-56">
      <select
        aria-label={t('common:attendees.filter_status_aria')}
        className={`${fieldCls} ${status ? 'border-2 border-primary font-semibold' : ''}`}
        value={status}
        onChange={(e) => update({ status: e.target.value, page: 1 })}
      >
        <option value="">{t('status:all')}</option>
        {STATUS_CODES.map((code) => (
          <option key={code} value={code}>
            {t(`status:${code}`)}
          </option>
        ))}
      </select>
    </div>
  )

  return (
    <div data-ds className="bg-section text-ink">
      <div className="mx-auto max-w-6xl px-4 py-6 md:px-8 md:py-8">
        <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl leading-8 font-semibold md:text-[28px] md:leading-9">{t('common:attendees.title')}</h1>
            <p className="text-sm leading-5 text-ink-2">{t('common:attendees.subtitle')}</p>
          </div>
          <Button variant="primary" type="button" onClick={() => navigate('/add')}>
            {t('common:attendees.add')}
          </Button>
        </header>

        <section aria-label={t('common:attendees.filters_aria')} className="mb-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-start">
            <div className="min-w-0 flex-1">
              <input
                type="search"
                aria-label={t('common:attendees.search_aria')}
                aria-describedby={hintId}
                placeholder={t('common:attendees.search_aria')}
                className={fieldCls}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
              <p id={hintId} className={`mt-1 text-sm leading-5 ${shortSearch ? 'text-warning' : 'text-ink-2'}`}>
                {shortSearch
                  ? t('common:attendees.search_short', { count: SEARCH_MIN_CHARS - typed })
                  : t('common:attendees.search_hint')}
              </p>
            </div>
            {isDesktop ? (
              statusSelect
            ) : (
              <div>
                <Button
                  variant="secondary"
                  type="button"
                  className="w-full"
                  aria-expanded={filtersOpen}
                  aria-controls={filtersId}
                  onClick={() => setFiltersOpen((v) => !v)}
                >
                  {status ? t('common:attendees.filters_count', { count: 1 }) : t('common:attendees.filters')}
                </Button>
                {filtersOpen && (
                  <div id={filtersId} className="mt-3 rounded-lg border border-line bg-surface p-3">
                    {statusSelect}
                  </div>
                )}
              </div>
            )}
            {hasFilters && (
              <Button variant="secondary" type="button" className={isDesktop ? '' : 'w-full'} onClick={resetFilters}>
                {t('common:attendees.reset')}
              </Button>
            )}
          </div>
        </section>

        {isError && (
          <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 rounded-lg bg-danger-bg p-4 text-danger">
            <span className="font-semibold">{t('common:attendees.load_error')}</span>
            <Button variant="secondary" type="button" disabled={isFetching} onClick={() => void refetch()}>
              {t('common:actions.retry')}
            </Button>
          </div>
        )}

        {isPending ? (
          <Skeleton />
        ) : (
          <>
            <p role="status" aria-live="polite" className="mb-2 text-sm leading-5 text-ink-2">
              {t('common:pagination.showing', { from, to, total })}
            </p>

            {rows.length === 0 && !isError ? (
              <EmptyState filtered={hasFilters} onReset={resetFilters} onAdd={() => navigate('/add')} />
            ) : isDesktop ? (
              <RegistryTable rows={rows} onOpen={open} />
            ) : (
              <RegistryCards rows={rows} onOpen={(id) => registryState.set({ lastOpenedId: id })} />
            )}

            {total > PAGE_SIZE && (
              <nav aria-label={t('common:attendees.pages_aria')} className="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-end">
                <Button
                  variant="secondary"
                  type="button"
                  disabled={isPlaceholderData || !data?.previous}
                  onClick={() => update({ page: Math.max(1, page - 1) })}
                >
                  {t('common:actions.prev')}
                </Button>
                <Button
                  variant="secondary"
                  type="button"
                  // При keepPreviousData `data.next` относится к прошлой странице во время
                  // загрузки — блокируем, чтобы двойной клик не перескочил последнюю (404).
                  disabled={isPlaceholderData || !data?.next}
                  onClick={() => update({ page: page + 1 })}
                >
                  {t('common:actions.next')}
                </Button>
              </nav>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function RegistryTable({ rows, onOpen }: { rows: Attendee[]; onOpen: (id: number) => void }) {
  const { t, i18n } = useTranslation()
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <table className="w-full table-fixed border-collapse text-base leading-6">
        <colgroup>
          <col className="w-[34%]" />
          <col className="w-[30%]" />
          <col className="w-[22%]" />
          <col className="w-[14%]" />
        </colgroup>
        <thead className="bg-section text-left text-sm leading-5 text-ink-2">
          <tr>
            <th scope="col" className="border-b border-line px-4 py-3 font-semibold">{t('common:attendees.col_attendee')}</th>
            <th scope="col" className="border-b border-line px-4 py-3 font-semibold">{t('common:attendees.col_request')}</th>
            <th scope="col" className="border-b border-line px-4 py-3 font-semibold">{t('common:attendees.col_status')}</th>
            <th scope="col" className="border-b border-line px-4 py-3 font-semibold">{t('common:attendees.col_added')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <tr
              key={a.id}
              className="cursor-pointer border-b border-line last:border-b-0 hover:bg-section"
              // Щелчок по строке — для мыши; с клавиатуры открывает ссылка с именем.
              onClick={() => onOpen(a.id)}
            >
              <td className="px-4 py-3 align-top">
                <Link
                  to={`/attendees/${a.id}`}
                  data-open-id={a.id}
                  className="font-semibold text-primary underline-offset-2 [overflow-wrap:anywhere] hover:underline"
                  onClick={(e) => {
                    e.stopPropagation()
                    registryState.set({ lastOpenedId: a.id })
                  }}
                >
                  {fullName(a)}
                </Link>
                {a.iin_masked && (
                  <div className="text-sm leading-5 text-ink-2">
                    {t('common:attendees.col_iin')} <span>{a.iin_masked}</span>
                  </div>
                )}
              </td>
              <td className="px-4 py-3 align-top [overflow-wrap:anywhere]">
                {a.request_name ? (
                  <div>{t('common:attendees.request', { name: a.request_name })}</div>
                ) : (
                  <div className="text-ink-2">—</div>
                )}
                {a.event_name && <div className="text-sm leading-5 text-ink-2">{a.event_name}</div>}
              </td>
              <td className="px-4 py-3 align-top">
                <StatusBadge status={a.status} returned={a.returned} />
              </td>
              <td className="px-4 py-3 align-top">{formatDate(a.dateAdd, i18n.language)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RegistryCards({ rows, onOpen }: { rows: Attendee[]; onOpen: (id: number) => void }) {
  const { t, i18n } = useTranslation()
  return (
    <ul className="space-y-3">
      {rows.map((a) => {
        const line = requestLine(a, t)
        return (
          <li key={a.id}>
            <Link
              to={`/attendees/${a.id}`}
              data-open-id={a.id}
              onClick={() => onOpen(a.id)}
              className="block rounded-lg border border-line bg-surface p-4 hover:border-field"
            >
              <span className="block font-semibold leading-6 [overflow-wrap:anywhere]">{fullName(a)}</span>
              <StatusBadge status={a.status} returned={a.returned} className="mt-2" />
              {line && <span className="mt-2 block text-sm leading-5 text-ink-2 [overflow-wrap:anywhere]">{line}</span>}
              <span className="mt-1 block text-sm leading-5 text-ink-2">
                {t('common:attendees.added_on', { date: formatDate(a.dateAdd, i18n.language) })}
                {a.iin_masked && (
                  <>
                    {' · '}
                    {t('common:attendees.col_iin')} <span>{a.iin_masked}</span>
                  </>
                )}
              </span>
              <span aria-hidden="true" className="mt-3 block font-semibold text-primary">
                {t('common:attendees.open_card')}
              </span>
            </Link>
          </li>
        )
      })}
    </ul>
  )
}

function EmptyState({ filtered, onReset, onAdd }: { filtered: boolean; onReset: () => void; onAdd: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-lg border border-line bg-surface p-6 text-center">
      {filtered ? (
        <>
          <p className="font-semibold">{t('common:attendees.empty')}</p>
          <p className="mt-1 text-sm text-ink-2">{t('common:attendees.empty_filtered_hint')}</p>
          <Button variant="secondary" type="button" className="mt-4" onClick={onReset}>
            {t('common:attendees.reset')}
          </Button>
        </>
      ) : (
        <>
          <p className="font-semibold">{t('common:attendees.empty_none')}</p>
          <p className="mt-1 text-sm text-ink-2">{t('common:attendees.empty_none_hint')}</p>
          <Button variant="primary" type="button" className="mt-4" onClick={onAdd}>
            {t('common:attendees.add_first')}
          </Button>
        </>
      )}
    </div>
  )
}

function Skeleton() {
  const { t } = useTranslation()
  return (
    <div aria-label={t('common:attendees.loading_list')} role="status" className="space-y-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-14 animate-pulse rounded-lg bg-line" />
      ))}
    </div>
  )
}
