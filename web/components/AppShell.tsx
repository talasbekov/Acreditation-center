"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { homeFor, isAdmin, isStaff, useAuth } from "@/lib/auth";
import { LANGS, useLang } from "@/lib/i18n";

const ROLE_LABEL: Record<string, string> = {
  superuser: "Администратор",
  superoperator: "Супероператор",
  operator: "Оператор",
  user: "Пользователь",
};

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { me, ready, logout } = useAuth();
  const { t, lang, setLang } = useLang();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!ready) return;
    if (!me) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    } else if (me.force_password_change && pathname !== "/change-password") {
      router.replace("/change-password");
    }
  }, [ready, me, pathname, router]);

  if (!ready || !me) {
    return <div className="flex min-h-screen items-center justify-center text-slate-400">{t("Загрузка…")}</div>;
  }

  const nav = me.force_password_change
    ? []
    : [
        { href: "/admin/events", label: t("Мероприятия"), show: isAdmin(me) },
        { href: "/admin/operators", label: t("Операторы"), show: isAdmin(me) },
        { href: "/admin/audit", label: t("Журнал аудита"), show: isAdmin(me) },
        { href: "/cabinet", label: t("Кабинет"), show: !isAdmin(me) },
        { href: "/staff", label: t("Проверка и выгрузка"), show: isStaff(me) },
      ].filter((n) => n.show);

  const active = (href: string) => pathname === href || pathname.startsWith(href + "/");
  const fullName = [me.first_name, me.last_name].filter(Boolean).join(" ") || me.username;

  const onLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        {t("К содержанию")}
      </a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link href={homeFor(me)} className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
              АЦ
            </span>
            <span className="leading-tight">
              <span className="block text-sm font-bold text-slate-900">{t("Аккредитационный центр")}</span>
              <span className="block text-xs text-slate-500">{t("Служба государственной охраны РК")}</span>
            </span>
          </Link>
          <nav className="flex flex-wrap gap-1" aria-label={t("Меню")}>
            {nav.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active(n.href) ? "page" : undefined}
                className={`rounded-lg px-3 py-2 text-sm font-medium ${
                  active(n.href) ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {n.label}
              </Link>
            ))}
            {isAdmin(me) && (
              <a href="/embankment/" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">
                {t("Администрирование")}
              </a>
            )}
          </nav>
          <div className="ml-auto flex flex-wrap items-center gap-3">
            <div className="flex overflow-hidden rounded-lg border border-slate-200" role="group" aria-label={t("Язык")}>
              {LANGS.map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => setLang(l)}
                  aria-pressed={lang === l}
                  className={`px-2.5 py-1 text-xs font-semibold uppercase ${
                    lang === l ? "bg-brand-600 text-white" : "bg-white text-slate-500 hover:bg-slate-50"
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
            <div className="text-right leading-tight">
              <div className="text-sm font-medium text-slate-800">{t("Добро пожаловать, {name}", { name: fullName })}</div>
              <div className="text-xs text-slate-500">{t(ROLE_LABEL[me.role] || me.role)}</div>
            </div>
            {!me.force_password_change && (
              <Link href="/change-password" className="btn-ghost">
                {t("Изменить пароль")}
              </Link>
            )}
            <button type="button" onClick={onLogout} className="btn-secondary">
              {t("Выйти")}
            </button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-7xl px-4 py-6">
        {children}
      </main>
    </div>
  );
}
