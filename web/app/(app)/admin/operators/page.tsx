"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { takeFlash } from "@/lib/flash";
import { useLang } from "@/lib/i18n";
import type { AdminHome } from "@/lib/types";
import AdminOnly from "@/components/admin/AdminOnly";
import OperatorCreateForm from "@/components/admin/OperatorCreateForm";
import Notice, { type NoticeValue } from "@/components/Notice";
import { Badge, PageHeader, Spinner } from "@/components/ui";

/** Главная администратора (`/avmac/`), часть «Пользователи»: создание оператора и список. */
function OperatorsPage() {
  const { t } = useLang();
  const [home, setHome] = useState<AdminHome | null>(null);
  const [notice, setNotice] = useState<NoticeValue>(null);
  const [q, setQ] = useState("");

  const load = useCallback(async () => setHome(await api<AdminHome>("/admin/home/")), []);
  useEffect(() => {
    const flash = takeFlash();
    if (flash) setNotice({ ok: true, text: flash });
    load().catch(() => setNotice({ ok: false, text: t("Не удалось подключиться к серверу") }));
  }, [load, t]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const all = home?.operators || [];
    if (!needle) return all;
    return all.filter((o) =>
      [o.last_name, o.first_name, o.patronymic, o.username, o.email, o.workplace].join(" ").toLowerCase().includes(needle),
    );
  }, [home, q]);

  if (!home) return <Spinner />;

  return (
    <div>
      <PageHeader title={t("Пользователи")} subtitle={`${t("Всего")}: ${home.operators.length}`} />
      <Notice value={notice} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <section className="card h-fit p-5" aria-labelledby="new-op">
          <h2 id="new-op" className="mb-4 text-lg font-semibold">
            {t("Новый оператор")}
          </h2>
          <OperatorCreateForm
            events={home.events}
            onDone={(text, ok) => {
              setNotice({ ok, text });
              load();
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          />
        </section>
        <section aria-labelledby="op-list">
          <h2 id="op-list" className="sr-only">
            {t("Пользователи")}
          </h2>
          <input
            className="input mb-3"
            type="search"
            placeholder={t("Поиск")}
            aria-label={t("Поиск")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <ul className="card divide-y divide-slate-100">
            {rows.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                <div>
                  <Link href={`/admin/operators/${o.id}`} className="font-medium text-brand-700 hover:underline">
                    {o.last_name} {o.first_name} {o.patronymic}
                  </Link>
                  <div className="text-xs text-slate-500">
                    {o.username}, {o.workplace}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  {!o.is_active && <Badge color="red">{t("Деактивирован")}</Badge>}
                  {o.role === "superoperator" && <Badge color="blue">{t("Супероператор")}</Badge>}
                  <span>{o.phone_number}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AdminOnly>
      <OperatorsPage />
    </AdminOnly>
  );
}
