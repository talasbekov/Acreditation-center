"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { AdminHome, EventBrief } from "@/lib/types";
import AdminOnly from "@/components/admin/AdminOnly";
import Notice, { type NoticeValue } from "@/components/Notice";
import { Field, PageHeader, Spinner, formatDate } from "@/components/ui";

const ASTANA = "1110106945";

/** Главная администратора (`/avmac/`), часть «Мероприятия»: создание и список на 900 дней. */
function EventsPage() {
  const { t } = useLang();
  const [home, setHome] = useState<AdminHome | null>(null);
  const [notice, setNotice] = useState<NoticeValue>(null);
  const empty = { name_rus: "", name_kaz: "", name_eng: "", event_code: "", date_start: "", date_end: "", city: ASTANA };
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => setHome(await api<AdminHome>("/admin/home/")), []);
  useEffect(() => {
    load().catch(() => setNotice({ ok: false, text: t("Не удалось подключиться к серверу") }));
  }, [load, t]);

  const set = (k: keyof typeof empty) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const r = await api<{ message: string }>("/admin/events/", { method: "POST", body: form });
      setNotice({ ok: true, text: r.message });
      setForm(empty);
      await load();
    } catch (ex) {
      setNotice({ ok: false, text: ex instanceof ApiException ? String(ex.problem.detail) : t("Не удалось подключиться к серверу") });
    } finally {
      setSaving(false);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const grant = async (ev: EventBrief, operatorId: string) => {
    if (!operatorId) return;
    try {
      const r = await api<{ message: string }>(`/admin/events/${ev.id}/operators/`, {
        method: "POST",
        body: { operator_ids: [Number(operatorId)] },
      });
      setNotice({ ok: true, text: r.message });
      await load();
    } catch (ex) {
      setNotice({ ok: false, text: ex instanceof ApiException ? String(ex.problem.detail) : t("Не удалось добавить пользователя.") });
    }
  };

  if (!home) return <Spinner />;

  return (
    <div>
      <PageHeader title={t("Мероприятия")} subtitle={t("Мероприятия, которые закончатся в ближайшие 900 дней")} />
      <Notice value={notice} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <section className="card h-fit p-5" aria-labelledby="new-event">
          <h2 id="new-event" className="mb-4 text-lg font-semibold">
            {t("Добавить мероприятие")}
          </h2>
          <form onSubmit={create} className="space-y-4">
            <Field label={t("Название мероприятия")} required hint="Название мероприятия на русском" htmlFor="name_rus">
              <input id="name_rus" className="input" required minLength={3} value={form.name_rus} onChange={set("name_rus")} />
            </Field>
            <Field label="Атауы" required hint="Жиынның атын қазақша жазыңыз" htmlFor="name_kaz">
              <input id="name_kaz" className="input" required minLength={3} value={form.name_kaz} onChange={set("name_kaz")} />
            </Field>
            <Field label="Event" required hint="Write event name in English" htmlFor="name_eng">
              <input id="name_eng" className="input" required minLength={3} value={form.name_eng} onChange={set("name_eng")} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("Код мероприятия")} required htmlFor="event_code">
                <input id="event_code" className="input" required maxLength={20} value={form.event_code} onChange={set("event_code")} />
              </Field>
              <Field label={t("Город")} htmlFor="city">
                <select id="city" className="input" value={form.city} onChange={set("city")}>
                  {home.cities.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name_rus}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("Дата начала")} required htmlFor="date_start">
                <input id="date_start" type="date" className="input" required value={form.date_start} onChange={set("date_start")} />
              </Field>
              <Field label={t("Дата окончания")} required htmlFor="date_end">
                <input id="date_end" type="date" className="input" required value={form.date_end} onChange={set("date_end")} />
              </Field>
            </div>
            <button type="submit" className="btn-primary w-full" disabled={saving}>
              {t("Добавить мероприятие")}
            </button>
          </form>
        </section>

        <section aria-labelledby="events-list">
          <h2 id="events-list" className="mb-3 text-lg font-semibold">
            {t("Список мероприятий")} <span className="text-slate-400">({home.events.length})</span>
          </h2>
          <ul className="space-y-3">
            {home.events.map((ev) => {
              const without = home.operators.filter((o) => !o.event_ids?.includes(ev.id));
              return (
                <li key={ev.id} className="card p-4">
                  <Link href={`/admin/events/${ev.id}`} className="text-base font-semibold text-brand-700 hover:underline">
                    {ev.name_rus}
                  </Link>
                  <p className="text-sm text-slate-500">
                    {formatDate(ev.date_start)} – {formatDate(ev.date_end)}
                    {ev.event_code && <> · {ev.event_code}</>}
                  </p>
                  {without.length > 0 && (
                    <form
                      className="mt-3 flex flex-wrap items-end gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const sel = (e.currentTarget.elements.namedItem("operator_id") as HTMLSelectElement).value;
                        grant(ev, sel);
                      }}
                    >
                      <label className="min-w-56 flex-1">
                        <span className="label">{t("Пользователь")}</span>
                        <select name="operator_id" className="input">
                          {without.map((o) => (
                            <option key={o.id} value={o.id}>
                              {o.last_name} {o.first_name} {o.patronymic} ({o.username})
                            </option>
                          ))}
                        </select>
                      </label>
                      <button type="submit" className="btn-secondary">
                        {t("Предоставить доступ")}
                      </button>
                    </form>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AdminOnly>
      <EventsPage />
    </AdminOnly>
  );
}
