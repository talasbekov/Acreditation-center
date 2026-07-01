import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router-dom'
import { getAttendees } from '@/api/attendees'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { useRole } from '@/hooks/useRole'
import { visibleNavItems } from './navConfig'

/**
 * Story fe-2.2 — единый каркас приложения: skip-link → header → [левый role-filtered nav | main].
 *
 * Лендмарки: <header> / <nav aria-label> / <main id="main-content">. Дети роутов рендерятся
 * в <main> через <Outlet/>. Активный пункт — токены nav-item-active (bg-primary-tint / text-primary
 * / font-semibold) + aria-current="page" (ставит NavLink). Skip-link — первый фокусируемый элемент,
 * скрыт до фокуса (WCAG 2.4.1), ведёт в <main>.
 *
 * Границы: ThemeToggle + финальная полировка шапки — fe-2.3; axe-гейт/focus-trap — fe-2.5.
 */
export function AppShell() {
  const { t } = useTranslation()
  const role = useRole()
  const items = visibleNavItems(role)

  // fe-3.7 (AC-2): бейдж-счётчик возвратов на пункте «Возвраты» (nav:notifications) —
  // виден на ЛЮБОМ экране оператора (AppShell оборачивает всё). Источник — returned-queryset
  // (in-app-петля без Telegram; когда hd-2-3 придёт — читать тот же источник, не дубль).
  // enabled только когда пункт виден роли (operator/superoperator/superuser).
  const showReturns = items.some((item) => item.key === 'nav:notifications')
  const { data: returnsCount = 0 } = useQuery({
    queryKey: ['returns-count'],
    queryFn: async () => (await getAttendees({ returned: true, page_size: 1 }))?.count ?? 0,
    enabled: showReturns,
    staleTime: 30_000,
  })

  return (
    <div className="relative flex min-h-svh flex-col">
      {/* skip-link: первый в DOM/фокусе, скрыт до фокуса, ведёт в <main> (WCAG 2.4.1) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        {t('nav:skip_to_content')}
      </a>

      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
        <span className="text-sm font-semibold text-text">{t('nav:app_title')}</span>
        <LanguageSwitcher />
      </header>

      <div className="flex flex-1">
        <nav
          aria-label={t('nav:primary')}
          className="w-56 shrink-0 border-r border-border bg-surface p-2"
        >
          <ul className="flex flex-col gap-1">
            {items.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  end={item.path === '/'}
                  className={({ isActive }) =>
                    'block rounded-md px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ' +
                    (isActive
                      ? 'bg-primary-tint font-semibold text-primary'
                      : 'text-text-muted hover:bg-surface-muted')
                  }
                >
                  {t(item.key)}
                  {item.key === 'nav:notifications' && returnsCount > 0 && (
                    <span
                      aria-label={t('reviewQueue:inbox_badge_aria', { count: returnsCount })}
                      className="ml-2 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-status-rejected px-1.5 text-xs font-semibold text-primary-foreground"
                    >
                      {returnsCount > 99 ? '99+' : returnsCount}
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* tabIndex={-1}: skip-link реально переводит фокус в контент (фокус не остаётся на ссылке). */}
        <main id="main-content" tabIndex={-1} className="flex-1 focus:outline-none">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
