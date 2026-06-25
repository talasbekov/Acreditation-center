import { useEffect, useRef, useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getAttendees, type AttendeeListParams } from '@/api/attendees'
import { Button } from '@/components/ui/button'

const PAGE_SIZE = 50
const SEARCH_DEBOUNCE_MS = 300
const SEARCH_MIN_CHARS = 3

const STATUS_OPTIONS = [
  { value: '', label: 'Все статусы' },
  { value: 'draft', label: 'Черновик' },
  { value: 'submitted', label: 'Отправлен' },
  { value: 'in_review', label: 'На проверке' },
  { value: 'ready', label: 'Готов' },
  { value: 'exported', label: 'Выгружен' },
] as const

const STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  submitted: 'Отправлен',
  in_review: 'На проверке',
  ready: 'Готов',
  exported: 'Выгружен',
}

const inputCls =
  'rounded-md border border-neutral-400 px-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-700'

function formatDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('ru-RU')
}

/** Список участников с поиском/фильтром/серверной пагинацией (Story 5.5). */
export function AttendeesPage() {
  const navigate = useNavigate()
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('') // debounced + ≥3 символов
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  // AC-2: поиск с debounce 300мс; запрос только при 3+ символах, иначе пусто.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const v = searchInput.trim()
      setSearch(v.length >= SEARCH_MIN_CHARS ? v : '')
      setPage(1)
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchInput])

  const params: AttendeeListParams = { page, page_size: PAGE_SIZE }
  if (search) params.search = search
  if (status) params.status = status

  const { data, isPending, isError, isPlaceholderData } = useQuery({
    queryKey: ['attendees', { search, status, page }],
    queryFn: () => getAttendees(params),
    placeholderData: keepPreviousData, // плавная пагинация (строки не «прыгают»)
  })

  const total = data?.count ?? 0
  const from = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const to = Math.min(page * PAGE_SIZE, total)

  return (
    <main className="mx-auto max-w-5xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-neutral-900">Участники</h1>
        <Button type="button" onClick={() => navigate('/add')}>
          Добавить
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <input
          aria-label="Поиск по ФИО"
          placeholder="Поиск по ФИО (от 3 символов)"
          className={`${inputCls} flex-1`}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select
          aria-label="Фильтр по статусу"
          className={status ? `${inputCls} border-blue-700 ring-2 ring-blue-700` : inputCls}
          value={status}
          onChange={(e) => {
            setStatus(e.target.value)
            setPage(1)
          }}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {isError && <p className="text-red-600">Не удалось загрузить список.</p>}

      {isPending ? (
        <SkeletonTable />
      ) : (
        <>
          <table className="w-full border-collapse text-base">
            <thead>
              <tr className="border-b border-neutral-300 text-left text-neutral-700">
                <th className="py-2 pr-3">ФИО</th>
                <th className="py-2 pr-3">ИИН</th>
                <th className="py-2 pr-3">Статус</th>
                <th className="py-2 pr-3">Добавлен</th>
                <th className="py-2">Действия</th>
              </tr>
            </thead>
            <tbody>
              {data && data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-neutral-500">
                    Ничего не найдено
                  </td>
                </tr>
              )}
              {data?.results.map((a) => (
                <tr
                  key={a.id}
                  className="cursor-pointer border-b border-neutral-200 hover:bg-neutral-50"
                  onClick={() => navigate(`/attendees/${a.id}`)}
                >
                  <td className="py-2 pr-3">
                    {[a.surname, a.firstname, a.patronymic].filter(Boolean).join(' ')}
                  </td>
                  <td className="py-2 pr-3">{a.iin_masked || '—'}</td>
                  <td className="py-2 pr-3">{STATUS_LABELS[a.status] ?? a.status}</td>
                  <td className="py-2 pr-3">{formatDate(a.dateAdd)}</td>
                  <td className="py-2">
                    <Button
                      variant="outline"
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/attendees/${a.id}`)
                      }}
                    >
                      Открыть
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mt-4 flex items-center justify-between">
            <span className="text-sm text-neutral-700">
              Показано {from}–{to} из {total}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                type="button"
                disabled={isPlaceholderData || !data?.previous}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Назад
              </Button>
              <Button
                variant="outline"
                type="button"
                // isPlaceholderData: при keepPreviousData `data.next` относится к
                // ПРЕДЫДУЩей странице во время фетча → блокируем клик до загрузки,
                // иначе быстрый двойной клик перескочит последнюю страницу (404).
                disabled={isPlaceholderData || !data?.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Вперёд
              </Button>
            </div>
          </div>
        </>
      )}
    </main>
  )
}

function SkeletonTable() {
  return (
    <div aria-label="Загрузка списка" className="space-y-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="h-10 animate-pulse rounded bg-neutral-200" />
      ))}
    </div>
  )
}
