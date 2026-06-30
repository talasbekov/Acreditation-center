import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  approveReviewQueueItem,
  getReviewQueue,
  returnReviewQueueItem,
  type ReviewQueueParams,
} from '@/api/reviewQueue'
import type { ReviewQueueItem } from '@/api/reviewQueue.schema'
import { ApiError } from '@/api/client'
import { mapApiError } from '@/errors/mapApiError'
import { PROBLEM_FLAGS } from '@/types/problemFlags'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { ReturnReasonDialog } from '@/components/ReturnReasonDialog'

const PAGE_SIZE = 50
const SEARCH_DEBOUNCE_MS = 300
const SEARCH_MIN_CHARS = 3
// fe-3.4 — длительность тающей анимации строки после одобрения (motion-safe). Должна
// совпадать с motion-safe:duration-300 на строке: по истечении — focus-landing + ре-фетч.
const FADE_MS = 300
// fe-3.5 — окно «Отменить» для оптимистично-отложенного возврата (Q1 default).
const UNDO_MS = 3000

/** fe-3.4 (AC-4): prefers-reduced-motion → одобренная строка исчезает мгновенно, без анимации. */
function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

/** Иммутабельные операции над Set id строк (review P2 — состояние одобрения по-строчно). */
function setWith(src: ReadonlySet<number>, id: number): Set<number> {
  const next = new Set(src)
  next.add(id)
  return next
}
function setWithout(src: ReadonlySet<number>, id: number): Set<number> {
  const next = new Set(src)
  next.delete(id)
  return next
}

// AC-2: статус-фильтр предлагает ТОЛЬКО значения очереди (submitted|in_review) — backend
// отвергает остальные 400. '' = «Все статусы» (без параметра). См. fe-3.1 query-контракт.
const QUEUE_STATUS_VALUES = ['', 'submitted', 'in_review'] as const
const PROBLEM_VALUES = ['', ...PROBLEM_FLAGS] as const

// Токен-утилиты (R2): без сырых neutral-*/hex — dark-safe «Тихий сланец».
const cellCls = 'px-[var(--cell-x)] py-[var(--row-y)] text-left align-middle text-[13px] leading-[1.4]'
const headCls =
  'px-[var(--cell-x)] py-2 text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-text-muted'

/** fe-3.2 — короткая локализованная метка проблемного флага (колонка «Проблема»). */
function flagLabel(t: (k: string) => string, flag: string): string {
  return t(`reviewQueue:flag_${flag}`)
}

/**
 * Story fe-3.2 — Очередь проверки (admin). Плотная доступная таблица заявок «На проверке»
 * против замороженного контракта fe-3.1. URL-state фильтры (shareable), серверная пагинация,
 * флаг-строки, ARIA roving-tabindex. Границы: bulk → E3b; detail-страница → 3.3 (ссылаемся на
 * `/queue/:id`); диалог возврата → 3.5 (`?action=return` — шов).
 */
export function ReviewQueuePage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()

  // Состояние фильтров/страницы — в URL (AC-2, R1). Read-path санитизируется (code-review
  // P2/P3/P6): deep-link/bookmark не должен слать значения, отвергаемые UI-контролами
  // (иначе backend 400 + React controlled-select warning + ложный filtersActive).
  const search = searchParams.get('search') ?? ''
  const rawStatus = searchParams.get('status') ?? ''
  const rawProblem = searchParams.get('problem') ?? ''
  const rawSubEvent = searchParams.get('sub_event_id') ?? '' // deep-link (чип-пикер → hd-5-6, Q2)
  const status = (QUEUE_STATUS_VALUES as readonly string[]).includes(rawStatus) ? rawStatus : ''
  const problem = (PROBLEM_VALUES as readonly string[]).includes(rawProblem) ? rawProblem : ''
  const validSubEventId =
    /^\d+$/.test(rawSubEvent) && Number(rawSubEvent) > 0 ? Number(rawSubEvent) : null
  const page = Math.max(1, Number(searchParams.get('page')) || 1)

  const [searchInput, setSearchInput] = useState(search)
  const searchRef = useRef<HTMLInputElement>(null)
  // fe-3.4 (review P2) — состояние одобрения ПО-СТРОЧНО (Set, не единичный id): мульти-approve
  // двух строк подряд иначе клобберил бы анимацию/disabled соседа. pendingIds — запрос в полёте
  // (кнопка disabled, без анимации); fadingIds — успех, строка тает.
  const [pendingIds, setPendingIds] = useState<ReadonlySet<number>>(() => new Set())
  const [fadingIds, setFadingIds] = useState<ReadonlySet<number>>(() => new Set())
  // fe-3.5 — id строки, для которой открыт ReturnReasonDialog (инлайн-возврат, Q3 default).
  const [returnTargetId, setReturnTargetId] = useState<number | null>(null)
  // review P3 — незавершённые fade-таймеры (чистим при unmount: иначе finish() сделает
  // setState/focus на размонтированном). review P4 — живой снимок results (отложенный
  // finish() не опирается на stale-замыкание индекса/списка).
  const fadeTimersRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set())
  const resultsRef = useRef<ReviewQueueItem[]>([])
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  // Помечает `search`, записанный НАМИ (debounce), чтобы sync-эффект (P5) не клобберил
  // активный ввод и реагировал только на внешнюю навигацию (browser back/forward).
  const lastSyncedSearch = useRef(search)

  // Дебаунс поиска → URL `search` (мин. 3 символа). Сброс на стр.1 только при реальном
  // изменении (иначе mount/повторный рендер сбрасывал бы страницу). replace — не засоряем history.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const v = searchInput.trim()
      const next = v.length >= SEARCH_MIN_CHARS ? v : ''
      lastSyncedSearch.current = next
      setSearchParams(
        (prev) => {
          const p = new URLSearchParams(prev)
          if ((p.get('search') ?? '') === next) return p
          if (next) p.set('search', next)
          else p.delete('search')
          p.delete('page')
          return p
        },
        { replace: true },
      )
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchInput, setSearchParams])

  // P5: URL → инпут при внешней навигации (back/forward). Не клобберит активный ввод —
  // реагирует только на `search`, который сменили НЕ мы (см. lastSyncedSearch).
  useEffect(() => {
    if (search !== lastSyncedSearch.current) {
      setSearchInput(search)
      lastSyncedSearch.current = search
    }
  }, [search])

  function setFilter(key: string, value: string) {
    setSearchParams((prev) => {
      const p = new URLSearchParams(prev)
      if (value) p.set(key, value)
      else p.delete(key)
      p.delete('page') // любой фильтр → стр.1
      return p
    })
  }

  // P6 (review): useCallback + dep в 404-эффекте ниже — стабильная ссылка, честный
  // exhaustive-deps (раньше goToPage пересоздавался каждый рендер и был опущен в deps).
  const goToPage = useCallback(
    (n: number) => {
      setSearchParams((prev) => {
        const p = new URLSearchParams(prev)
        if (n > 1) p.set('page', String(n))
        else p.delete('page')
        return p
      })
    },
    [setSearchParams],
  )

  const params: ReviewQueueParams = { page, page_size: PAGE_SIZE }
  if (search && search.length >= SEARCH_MIN_CHARS) params.search = search // P6: min-3 и в read-path
  if (status) params.status = status
  if (problem) params.problem = problem
  if (validSubEventId !== null) params.sub_event_id = validSubEventId

  const { data, isPending, isError, error, isPlaceholderData } = useQuery({
    queryKey: [
      'review-queue',
      { search: params.search ?? '', status, problem, subEventId: validSubEventId, page },
    ],
    queryFn: () => getReviewQueue(params),
    placeholderData: keepPreviousData,
  })

  const total = data?.count ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  // P1 [High]: bookmark/deep-link на out-of-range страницу → DRF PageNumberPagination 404.
  // Очередь естественно опустошается → восстанавливаемся на стр.1 (а не generic-error-тупик).
  useEffect(() => {
    if (isError && error instanceof ApiError && error.status === 404 && page > 1) {
      goToPage(1)
    }
  }, [isError, error, page, goToPage])

  const displayPage = Math.min(page, pages)
  const from = total === 0 ? 0 : (displayPage - 1) * PAGE_SIZE + 1
  const to = Math.min(displayPage * PAGE_SIZE, total)
  const results = data?.results ?? []
  resultsRef.current = results // review P4 — finish() читает живой список, не stale-замыкание
  // P3: filtersActive — по ЭФФЕКТИВНЫМ (отправленным) фильтрам, иначе невалидный
  // sub_event_id / <3-симв поиск ложно показывал бы «не найдено» вместо «всё проверено».
  const filtersActive = Boolean(params.search || status || problem || validSubEventId !== null)

  // review P3 — чистим висящие fade-таймеры при размонтировании (иначе finish() сделает
  // setState/focus на уже отсоединённом компоненте — утечка жизненного цикла).
  useEffect(() => {
    const timers = fadeTimersRef.current
    return () => {
      timers.forEach((id) => window.clearTimeout(id))
      timers.clear()
    }
  }, [])

  const isForbidden = isError && error instanceof ApiError && error.status === 403
  const errorText = isForbidden ? t('reviewQueue:no_access') : t('reviewQueue:load_error')

  // Roving-tabindex (AC-4): ОДНА точка входа по Tab, стрелки двигают фокус по строкам,
  // Enter открывает detail. Действия в строке — tabIndex=-1 (Tab выходит из таблицы, не
  // через 50 строк). Native <table> + <th scope> сохранены (лучшая поддержка SR).
  const [activeRow, setActiveRow] = useState(0)
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([])
  const activeIndex = results.length ? Math.min(activeRow, results.length - 1) : 0

  // P4: сбрасываем roving-точку входа при смене страницы/фильтра — иначе tabIndex=0
  // остаётся на клампнутой нижней строке и Tab входит в середину новой таблицы.
  useEffect(() => {
    setActiveRow(0)
  }, [page, status, problem, validSubEventId, params.search])

  function focusRow(idx: number) {
    const clamped = Math.max(0, Math.min(idx, results.length - 1))
    setActiveRow(clamped)
    rowRefs.current[clamped]?.focus()
  }

  function onRowKeyDown(e: React.KeyboardEvent<HTMLTableRowElement>, i: number, id: number) {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        focusRow(i + 1)
        break
      case 'ArrowUp':
        e.preventDefault()
        focusRow(i - 1)
        break
      case 'Home':
        e.preventDefault()
        focusRow(0)
        break
      case 'End':
        e.preventDefault()
        focusRow(results.length - 1)
        break
      case 'Enter':
        e.preventDefault()
        // review P9 — не уводим в detail заявку, которая прямо сейчас одобряется/тает
        // (pointer-events-none блокирует мышь, но не клавиатуру; цель уже покинула очередь).
        if (!pendingIds.has(id) && !fadingIds.has(id)) navigate(`/queue/${id}`)
        break
    }
  }

  // fe-3.4 — одобрение из строки очереди. Состояние в полёте/таяния — в pendingIds/fadingIds
  // (review P2), не в общем approveMutation.variables (тот хранит лишь ПОСЛЕДНИЙ id → ложно
  // re-enable соседа при мульти-approve). 409/ошибка → toast через FE-маппер fe-1.2.
  const approveMutation = useMutation({
    mutationFn: (id: number) => approveReviewQueueItem(id),
    onError: (e, id) => {
      setPendingIds((prev) => setWithout(prev, id))
      if (e instanceof ApiError) {
        toast.error(mapApiError(e.problem, t, i18n))
        // review P5 — 409 = строка устарела (заявка уже не in_review). Иначе она зависла бы
        // в очереди с вечно-409-ящей кнопкой; ре-фетч сводит UI к серверной истине.
        if (e.status === 409) void queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      } else {
        toast.error(t('common:network_error'))
      }
    },
  })

  // AC-4 «куда делась заявка»: одобренная строка тает, фокус приземляется на СОСЕДА (не в
  // body). review P4 — индекс ищем в ЖИВОМ resultsRef по id (а не по stale-замыканию i):
  // фоновый рефетч за время FADE_MS мог сдвинуть/убрать строку. Любой промах ref → фолбэк
  // в поле поиска, чтобы фокус никогда не проваливался в document.body.
  function focusOrSearch(node: HTMLTableRowElement | null) {
    if (node) node.focus()
    else searchRef.current?.focus()
  }
  function landFocusAfterDecision(id: number) {
    const list = resultsRef.current
    if (list.length <= 1) {
      // Очередь опустела → фокус в поле поиска (заголовок не фокусируем — нет интерактива).
      setActiveRow(0)
      searchRef.current?.focus()
      return
    }
    const idx = list.findIndex((r) => r.id === id)
    if (idx === -1) {
      // Строку уже убрал рефетч → держим фокус в текущем активном диапазоне (clamp), не в body.
      const fallback = Math.min(activeRow, list.length - 1)
      setActiveRow(fallback)
      focusOrSearch(rowRefs.current[fallback])
    } else if (idx < list.length - 1) {
      setActiveRow(idx) // следующая строка после удаления займёт индекс idx
      focusOrSearch(rowRefs.current[idx + 1])
    } else {
      setActiveRow(idx - 1) // одобрили последнюю → предыдущая
      focusOrSearch(rowRefs.current[idx - 1])
    }
  }

  function handleApprove(id: number) {
    setPendingIds((prev) => setWith(prev, id)) // в полёте: кнопка disabled (P2/B3), без анимации
    approveMutation.mutate(id, {
      onSuccess: () => {
        toast.success(t('reviewQueue:approve_toast_success')) // простой success, БЕЗ undo (это fe-3.5)
        setPendingIds((prev) => setWithout(prev, id))
        setFadingIds((prev) => setWith(prev, id)) // тающая анимация (motion-safe); reduced → мгновенно
        const finish = () => {
          landFocusAfterDecision(id)
          void queryClient.invalidateQueries({ queryKey: ['review-queue'] }) // сервер-истина
          setFadingIds((prev) => setWithout(prev, id))
        }
        if (prefersReducedMotion()) finish()
        else {
          const timer = window.setTimeout(() => {
            fadeTimersRef.current.delete(timer) // review P3 — таймер отработал, убираем из набора
            finish()
          }, FADE_MS)
          fadeTimersRef.current.add(timer)
        }
      },
    })
  }

  // fe-3.5 — возврат из строки. Оптимистично-отложенный POST (Q1 default): на confirm строка
  // тает + undo-toast; реальный /return/ по таймеру (UNDO_MS), «Отменить» отменяет до вызова
  // (нет компенсирующего перехода/двойного аудита). Reuse fade/focus-машинерии approve.
  const returnMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      returnReviewQueueItem(id, reason),
    onError: (e, { id }) => {
      setFadingIds((prev) => setWithout(prev, id)) // POST не прошёл → возвращаем строку
      if (e instanceof ApiError) {
        toast.error(mapApiError(e.problem, t, i18n))
        if (e.status === 409) void queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      } else {
        toast.error(t('common:network_error'))
      }
    },
  })

  function handleReturn(id: number, reason: string) {
    setReturnTargetId(null) // закрыть диалог
    setFadingIds((prev) => setWith(prev, id)) // оптимистично прячем строку (тает)
    landFocusAfterDecision(id) // фокус на соседа сразу (строка покидает очередь)
    const timer = window.setTimeout(() => {
      fadeTimersRef.current.delete(timer)
      returnMutation.mutate(
        { id, reason },
        { onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: ['review-queue'] }) // сервер-истина
          setFadingIds((prev) => setWithout(prev, id))
        } },
      )
    }, UNDO_MS)
    fadeTimersRef.current.add(timer)
    toast.success(t('reviewQueue:return_toast_success'), {
      duration: UNDO_MS,
      action: {
        label: t('reviewQueue:undo'),
        onClick: () => {
          window.clearTimeout(timer)
          fadeTimersRef.current.delete(timer)
          setFadingIds((prev) => setWithout(prev, id)) // отмена до вызова → строка восстановлена
        },
      },
    })
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="mb-4 text-[15px] font-[650] tracking-[-0.01em] text-text">
        {t('reviewQueue:title')}
      </h1>

      <div className="mb-4 flex flex-wrap gap-3">
        <input
          ref={searchRef}
          aria-label={t('reviewQueue:search_aria')}
          placeholder={t('reviewQueue:search_placeholder')}
          className="flex-1 rounded-md border border-input-border bg-surface px-3 text-base text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select
          aria-label={t('reviewQueue:filter_status_aria')}
          className={
            'rounded-md border bg-surface px-3 text-base text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ' +
            (status ? 'border-primary ring-2 ring-primary' : 'border-input-border')
          }
          value={status}
          onChange={(e) => setFilter('status', e.target.value)}
        >
          {QUEUE_STATUS_VALUES.map((v) => (
            <option key={v} value={v}>
              {v === '' ? t('status:all') : t(`status:${v}`)}
            </option>
          ))}
        </select>
        <select
          aria-label={t('reviewQueue:filter_problem_aria')}
          className={
            'rounded-md border bg-surface px-3 text-base text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ' +
            (problem ? 'border-primary ring-2 ring-primary' : 'border-input-border')
          }
          value={problem}
          onChange={(e) => setFilter('problem', e.target.value)}
        >
          {PROBLEM_VALUES.map((v) => (
            <option key={v} value={v}>
              {v === '' ? t('reviewQueue:filter_problem_all') : flagLabel(t, v)}
            </option>
          ))}
        </select>
      </div>

      {searchInput.trim().length > 0 && searchInput.trim().length < SEARCH_MIN_CHARS && (
        <p className="mb-4 text-sm text-text-muted">{t('validation:search_min_chars')}</p>
      )}

      {isError && <p className="text-status-rejected">{errorText}</p>}

      {!isError && (
        <p className="sr-only" aria-live="polite">
          {/* P8 (review): для пустой очереди не анонсируем «страница 1 из 1» (противоречие для SR). */}
          {total === 0
            ? t('reviewQueue:table_aria_empty')
            : t('reviewQueue:table_aria', { total, page: displayPage, pages })}
        </p>
      )}

      {isPending ? (
        <SkeletonTable />
      ) : isError ? null : results.length === 0 ? (
        <EmptyState filtersActive={filtersActive} />
      ) : (
        <>
          <table
            className="w-full border-separate border-spacing-y-1.5 text-text"
            aria-label={t('reviewQueue:title')}
          >
            <thead>
              <tr>
                <th scope="col" className={headCls}>{t('reviewQueue:col_full_name')}</th>
                <th scope="col" className={headCls}>{t('reviewQueue:col_iin')}</th>
                <th scope="col" className={headCls}>{t('reviewQueue:col_sub_event')}</th>
                <th scope="col" className={headCls}>{t('reviewQueue:col_status')}</th>
                <th scope="col" className={headCls}>{t('reviewQueue:col_problem')}</th>
                <th scope="col" className={`${headCls} text-right`}>{t('reviewQueue:col_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {results.map((item, i) => {
                const flagged = item.problem_flags.length > 0
                const approving = fadingIds.has(item.id) // review P2 — таяние по fadingIds
                const rowBusy = pendingIds.has(item.id) || fadingIds.has(item.id)
                return (
                  <tr
                    key={item.id}
                    ref={(el) => {
                      rowRefs.current[i] = el
                    }}
                    tabIndex={i === activeIndex ? 0 : -1}
                    onFocus={() => setActiveRow(i)}
                    onKeyDown={(e) => onRowKeyDown(e, i, item.id)}
                    onClick={() => navigate(`/queue/${item.id}`)}
                    className={
                      'cursor-pointer rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ' +
                      (flagged
                        ? 'bg-status-rejected-tint [&>*:first-child]:border-l-[3px] [&>*:first-child]:border-status-rejected'
                        : 'bg-surface hover:bg-surface-muted') +
                      // AC-4: тающая строка одобрения. motion-safe → плавно; prefers-reduced-motion
                      // не применит opacity-0 → строка исчезает мгновенно при ре-фетче (без анимации).
                      (approving
                        ? ' pointer-events-none motion-safe:opacity-0 motion-safe:transition-opacity motion-safe:duration-300'
                        : '')
                    }
                  >
                    <th scope="row" className={`${cellCls} rounded-l-md font-normal`}>
                      {item.full_name}
                    </th>
                    <td className={`${cellCls} tabular-nums text-text-muted`}>
                      {item.iin_masked || '—'}
                    </td>
                    <td className={cellCls}>{item.sub_event_name ?? '—'}</td>
                    <td className={cellCls}>
                      <StatusBadge status={item.status} />
                    </td>
                    <td className={cellCls}>
                      {flagged ? (
                        <span className="flex flex-wrap gap-1">
                          {item.problem_flags.map((f) => (
                            <span
                              key={f}
                              className="rounded-full bg-status-rejected-tint px-2 py-0.5 text-xs font-medium text-status-rejected"
                            >
                              {flagLabel(t, f)}
                            </span>
                          ))}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className={`${cellCls} rounded-r-md text-right`}>
                      <span className="inline-flex gap-2">
                        <Link
                          to={`/queue/${item.id}`}
                          tabIndex={-1}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex h-9 items-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                        >
                          {t('reviewQueue:action_review')}
                        </Link>
                        {/* fe-3.4 — быстрое одобрение из строки. review P1 — кнопка ТОЛЬКО для
                            in_review: submitted→ready запрещён FSM (всегда 409), не предлагаем
                            заведомо падающее действие. tabIndex=-1 (roving-tabindex); disabled —
                            по pendingIds/fadingIds (review P2/B3), не по общему mutation.variables. */}
                        {item.status === 'in_review' && (
                          <button
                            type="button"
                            tabIndex={-1}
                            disabled={rowBusy}
                            onClick={(e) => {
                              e.stopPropagation()
                              handleApprove(item.id)
                            }}
                            className="inline-flex h-9 items-center rounded-md border border-status-active bg-status-active-tint px-3 text-sm font-medium text-status-active hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
                          >
                            {t('reviewQueue:approve_action')}
                          </button>
                        )}
                        {/* fe-3.5 — возврат из строки. Только для in_review (FSM submitted→submitted
                            =409, как approve-gate P1). Инлайн ReturnReasonDialog (Q3), tabIndex=-1;
                            disabled по rowBusy (в полёте/тает). */}
                        {item.status === 'in_review' && (
                          <button
                            type="button"
                            tabIndex={-1}
                            disabled={rowBusy}
                            onClick={(e) => {
                              e.stopPropagation()
                              setReturnTargetId(item.id)
                            }}
                            className="inline-flex h-9 items-center rounded-md border border-border-strong bg-surface px-3 text-sm font-medium text-text hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
                          >
                            {t('reviewQueue:action_return')}
                          </button>
                        )}
                      </span>
                    </td>
                  </tr>
                )
              })}
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
                onClick={() => goToPage(page - 1)}
              >
                {t('common:actions.prev')}
              </Button>
              <Button
                variant="outline"
                type="button"
                disabled={isPlaceholderData || !data?.next}
                onClick={() => goToPage(page + 1)}
              >
                {t('common:actions.next')}
              </Button>
            </div>
          </div>
        </>
      )}

      <ReturnReasonDialog
        open={returnTargetId !== null}
        onClose={() => setReturnTargetId(null)}
        onSubmit={(reason) => {
          if (returnTargetId !== null) handleReturn(returnTargetId, reason)
        }}
      />
    </div>
  )
}

/** AC-3: два разных пустых состояния — «всё проверено» (нет фильтров) vs «не найдено». */
function EmptyState({ filtersActive }: { filtersActive: boolean }) {
  const { t } = useTranslation()
  if (filtersActive) {
    return <p className="py-8 text-center text-text-muted">{t('reviewQueue:empty_no_match')}</p>
  }
  return (
    <div className="py-12 text-center">
      <p className="text-[15px] font-[650] text-text">{t('reviewQueue:empty_all_clear_title')}</p>
      <p className="mt-1 text-sm text-text-muted">{t('reviewQueue:empty_all_clear_body')}</p>
    </div>
  )
}

function SkeletonTable() {
  const { t } = useTranslation()
  return (
    <div aria-label={t('reviewQueue:loading_list')} className="space-y-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-md bg-surface-muted" />
      ))}
    </div>
  )
}
