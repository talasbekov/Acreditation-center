"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useLang, type Lang } from "@/lib/i18n";

const LANGS: Lang[] = ["ru", "kz", "en"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { session, ready, isAdmin, logout } = useAuth();
  const { t, lang, setLang } = useLang();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (ready && !session) router.replace("/login");
  }, [ready, session, router]);

  if (!ready || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        …
      </div>
    );
  }

  const nav = [
    { href: "/events", label: t("events"), icon: "📅", show: true },
    { href: "/operators", label: t("operators"), icon: "👥", show: isAdmin },
    { href: "/audit", label: t("audit"), icon: "📜", show: isAdmin },
  ].filter((n) => n.show);

  const active = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="min-h-screen lg:flex">
      {/* Sidebar */}
      <aside className="border-b border-slate-200 bg-white lg:fixed lg:inset-y-0 lg:w-64 lg:border-b-0 lg:border-r">
        <div className="flex items-center gap-2 px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            🛡️
          </div>
          <div>
            <div className="text-sm font-bold leading-tight text-slate-900">
              {t("appName")}
            </div>
            <div className="text-xs text-slate-400">СГО РК</div>
          </div>
        </div>
        <nav className="flex gap-1 px-3 pb-3 lg:flex-col">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active(n.href)
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              <span>{n.icon}</span>
              {n.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main */}
      <div className="flex min-h-screen flex-1 flex-col lg:pl-64">
        <header className="flex items-center justify-end gap-3 border-b border-slate-200 bg-white px-6 py-3">
          <div className="flex overflow-hidden rounded-lg border border-slate-200">
            {LANGS.map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`px-2.5 py-1 text-xs font-semibold uppercase ${
                  lang === l ? "bg-brand-600 text-white" : "bg-white text-slate-500 hover:bg-slate-50"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
          <Link href="/settings" className="text-right leading-tight hover:opacity-80">
            <div className="text-sm font-medium text-slate-800">
              {session.user.full_name}
            </div>
            <div className="text-xs text-slate-400">
              {isAdmin ? "Администратор" : "Оператор"}
            </div>
          </Link>
          <button onClick={logout} className="btn-secondary">
            {t("logout")}
          </button>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
