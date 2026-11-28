"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { isStaff, useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { ErrorBox } from "../ui";

/** Вкладки страниц проверки (как `ds_staff_base.html`) и проверка роли. */
export default function StaffShell({ eventId, children }: { eventId: string; children: React.ReactNode }) {
  const { me } = useAuth();
  const { t } = useLang();
  const pathname = usePathname();
  if (!isStaff(me)) return <ErrorBox text={t("Нет доступа к этой странице")} />;
  const tabs = [
    { href: `/staff/${eventId}/review`, label: t("Очередь проверки") },
    { href: `/staff/${eventId}/dashboard`, label: t("Дашборд и выгрузка") },
    { href: `/staff/${eventId}/badges`, label: t("Бейджи") },
  ];
  return (
    <div>
      <nav className="mb-4 flex flex-wrap gap-1 border-b border-slate-200" aria-label={t("Проверка и выгрузка")}>
        <Link href="/staff" className="px-3 py-2 text-sm text-slate-500 hover:text-slate-800">
          ← {t("Мероприятия")}
        </Link>
        {tabs.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={pathname === tab.href ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              pathname === tab.href ? "border-brand-600 text-brand-700" : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            {tab.label}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}
