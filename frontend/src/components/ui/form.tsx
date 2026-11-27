import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

// Этап D: общие элементы форм на токенах эталона (index.css, отчёт 05).

/** Поле ввода/выбора: 44 px, граница 4,6:1, ошибка — красная граница. */
export function fieldClass(invalid = false, extra = '') {
  return cn(
    'h-11 w-full rounded-md border bg-surface px-3 text-base text-ink placeholder:text-ink-2',
    'disabled:cursor-not-allowed disabled:bg-section disabled:text-ink-2',
    invalid ? 'border-2 border-danger' : 'border-field',
    extra,
  )
}

/** id подсказки и ошибки — для `aria-describedby` поля. */
export function describedBy(id: string, hint?: ReactNode, error?: string) {
  const ids = [hint ? `${id}-hint` : '', error ? `${id}-error` : ''].filter(Boolean)
  return ids.length ? ids.join(' ') : undefined
}

/** Раздел формы: заголовок и белая поверхность. */
export function FormSection({ title, description, children }: { title: string; description?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4 md:p-6">
      <h2 className="text-lg leading-7 font-semibold text-ink">{title}</h2>
      {description && <p className="mt-1 text-sm leading-5 text-ink-2">{description}</p>}
      <div className="mt-4 grid gap-4 md:grid-cols-2">{children}</div>
    </section>
  )
}

/**
 * Поле с меткой над контролом. Метка связана с контролом через `htmlFor`; признак
 * обязательности стоит рядом с меткой, а не внутри неё — так имя поля для диктора и
 * тестов остаётся точным («ИИН»), а обязательность сообщает `aria-required`.
 */
export function Field({
  id,
  label,
  required,
  hint,
  error,
  wide,
  children,
}: {
  id: string
  label: string
  required?: boolean
  hint?: ReactNode
  error?: string
  /** Во всю ширину раздела (на desktop раздел в две колонки). */
  wide?: boolean
  children: ReactNode
}) {
  return (
    <div className={cn('min-w-0', wide && 'md:col-span-2')}>
      <div className="mb-1 flex items-baseline gap-1">
        <label htmlFor={id} className="text-base leading-6 font-semibold text-ink">
          {label}
        </label>
        {required && (
          <span aria-hidden="true" className="font-semibold text-danger">
            *
          </span>
        )}
      </div>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-sm leading-5 text-ink-2">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1 text-sm leading-5 font-semibold text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

export interface SummaryItem {
  id: string
  label: string
  message: string
}

/** Сводка ошибок над формой: объявляется диктору, ссылки ведут к полям. */
export function ErrorSummary({ items }: { items: SummaryItem[] }) {
  return (
    <div role="alert" aria-labelledby="error-summary-title" className="rounded-lg border-2 border-danger bg-danger-bg p-4 text-danger">
      <h2 id="error-summary-title" className="font-semibold">
        Не сохранено: исправьте {items.length === 1 ? 'поле' : 'поля'}
      </h2>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={`#${item.id}`}
              className="underline underline-offset-2"
              onClick={(e) => {
                e.preventDefault()
                const el = document.getElementById(item.id)
                el?.focus()
                el?.scrollIntoView?.({ block: 'center' })
              }}
            >
              {item.label}: {item.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Шапка страницы формы: заголовок и короткая строка контекста. */
export function PageHeader({ title, context }: { title: ReactNode; context?: ReactNode }) {
  return (
    <header className="mb-5 min-w-0">
      <h1 className="text-2xl leading-8 font-semibold [overflow-wrap:anywhere] text-ink md:text-[28px] md:leading-9">{title}</h1>
      {context && <p className="mt-1 text-sm leading-5 text-ink-2 [overflow-wrap:anywhere]">{context}</p>}
    </header>
  )
}
