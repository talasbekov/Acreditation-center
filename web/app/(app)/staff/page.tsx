"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import type { EventBrief } from "@/lib/types";
import { ErrorBox, PageHeader, Spinner, formatDate } from "@/components/ui";

/** Выбор мероприятия для проверки и выгрузки (супероператор, администратор). */
export default function StaffEventsPage() {
  const { me } = useAuth();
  const { t, name } = useLang();
  const [events, setEvents] = useState<EventBrief[] | null>(null);

  useEffect(() => {
    if (isStaff(me)) api<{ events: EventBrief[] }>("/staff/events/").then((r) => setEvents(r.events));
  }, [me]);

  if (!isStaff(me)) return <ErrorBox text={t("Нет доступа к этой странице")} />;
  if (!events) return <Spinner />;

  return (
    <div>
      <PageHeader title={t("Проверка и выгрузка")} />
      <ul className="space-y-3">
        {events.map((ev) => (
          <li key={ev.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <div className="font-semibold">{name(ev)}</div>
              <div className="text-sm text-slate-500">
                {formatDate(ev.date_start)} – {formatDate(ev.date_end)} · {ev.event_code}
              </div>
            </div>
            <div className="flex gap-2">
              <Link className="btn-secondary" href={`/staff/${ev.id}/review`}>
                {t("Очередь проверки")}
              </Link>
              <Link className="btn-primary" href={`/staff/${ev.id}/dashboard`}>
                {t("Дашборд и выгрузка")}
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
