"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiException, downloadLegacy } from "@/lib/api";
import { setFlash, takeFlash } from "@/lib/flash";
import { useLang } from "@/lib/i18n";
import type { AdminEventCard, AdminRequestRow } from "@/lib/types";
import AdminOnly from "@/components/admin/AdminOnly";
import OperatorCreateForm from "@/components/admin/OperatorCreateForm";
import Notice, { type NoticeValue } from "@/components/Notice";
import { Badge, ConfirmButton, PageHeader, Spinner, formatDate, formatDateTime } from "@/components/ui";

const REQ_COLOR: Record<string, "gray" | "green" | "amber" | "blue"> = {
  Active: "gray",
  Checking: "gray",
  Sent: "amber",
  Exported: "green",
};

/** Карточка мероприятия администратора (`/show_event/<id>/`). */
function EventCard() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { t } = useLang();
  const [card, setCard] = useState<AdminEventCard | null>(null);
  const [notice, setNotice] = useState<NoticeValue>(null);
  const [selected, setSelected] = useState<string[]>([]);

  const load = useCallback(async () => setCard(await api<AdminEventCard>(`/admin/events/${id}/`)), [id]);
  useEffect(() => {
    const flash = takeFlash();
    if (flash) setNotice({ ok: true, text: flash });
    load().catch((e) =>
      setNotice({ ok: false, text: e instanceof ApiException && e.status === 404 ? t("Мероприятие не найдено") : t("Не удалось подключиться к серверу") }),
    );
  }, [load, t]);

  const fail = (e: unknown) =>
    setNotice({ ok: false, text: e instanceof ApiException ? String(e.problem.detail || e.message) : t("Не удалось подключиться к серверу") });

  const json = async (path: string, name: string) => {
    try {
      await downloadLegacy(path, name, "POST");
    } catch (e) {
      fail(e);
    }
  };

  const bind = async () => {
    if (!selected.length) return;
    try {
      const r = await api<{ message: string }>(`/admin/events/${id}/operators/`, {
        method: "POST",
        body: { operator_ids: selected.map(Number) },
      });
      setNotice({ ok: true, text: r.message });
      setSelected([]);
      await load();
    } catch (e) {
      fail(e);
    }
  };

  const unbind = async (operatorId: number) => {
    try {
      const r = await api<{ message: string }>(`/admin/events/${id}/operators/${operatorId}/`, { method: "DELETE" });
      setNotice({ ok: true, text: r.message });
      await load();
    } catch (e) {
      fail(e);
    }
  };

  const remove = async () => {
    try {
      const r = await api<{ message: string }>(`/admin/events/${id}/`, { method: "DELETE" });
      setFlash(r.message);
      router.push("/admin/events");
    } catch (e) {
      fail(e);
    }
  };

  if (!card) return notice ? <Notice value={notice} /> : <Spinner />;
  const ev = card.event;

  const requestRow = (r: AdminRequestRow, withJson: boolean) => (
    <li key={r.id} className="flex flex-wrap items-center gap-2 py-2">
      <Link href={`/requests/${r.id}`} className="font-medium text-brand-700 hover:underline">
        {r.name}
      </Link>
      <Badge color={REQ_COLOR[r.status] || "blue"}>{r.status}</Badge>
      <span className="text-sm text-slate-500">
        {t("от")} {r.created_by}
        {r.status === "Sent" || r.status === "Exported" ? ` · ${formatDateTime(r.registration_time)}` : ""}
      </span>
      {withJson && (
        <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => json(`/download_request_json/${r.id}/`, `request_${r.id}.json`)}>
          {t("Сверить номера участников заявки (JSON)")}
        </button>
      )}
    </li>
  );

  return (
    <div>
      <PageHeader title={ev.name_rus} subtitle={ev.event_code} back={{ href: "/admin/events", label: t("Мероприятия") }} />
      <Notice value={notice} />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <section className="card p-5" aria-labelledby="ev-info">
            <h2 id="ev-info" className="mb-3 text-lg font-semibold">
              {t("Мероприятие")}
            </h2>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
              <dt className="text-slate-500">Название</dt>
              <dd>{ev.name_rus}</dd>
              <dt className="text-slate-500">Атауы</dt>
              <dd>{ev.name_kaz}</dd>
              <dt className="text-slate-500">Event</dt>
              <dd>{ev.name_eng}</dd>
              <dt className="text-slate-500">{t("Начало")}</dt>
              <dd>{formatDate(ev.date_start)}</dd>
              <dt className="text-slate-500">{t("Окончание")}</dt>
              <dd>{formatDate(ev.date_end)}</dd>
              <dt className="text-slate-500">{t("Город")}</dt>
              <dd>{card.city_name}</dd>
            </dl>
          </section>

          <section className="card p-5" aria-labelledby="ev-files">
            <h2 id="ev-files" className="mb-1 text-lg font-semibold">
              {t("Внутренняя сверка идентификаторов")}
            </h2>
            <p className="mb-3 text-sm text-slate-500">
              {t("JSON содержит только внутренние номера. Заявки сохраняют свой статус и очередь на официальную выгрузку.")}
            </p>
            <div className="flex flex-col items-start gap-2">
              <button type="button" className="btn-secondary" onClick={() => json(`/download_all_guests_json/${ev.id}/`, `event_${ev.id}_all.json`)}>
                {t("Сверить номера всех участников (JSON)")}
              </button>
              {card.unexported > 0 && (
                <button type="button" className="btn-secondary" onClick={() => json(`/download_guests_json/${ev.id}/`, `event_${ev.id}_new.json`)}>
                  {t("Сверить номера участников из {n} новых заявок", { n: card.unexported })} <Badge color="red">!</Badge>
                </button>
              )}
              <a className="btn-secondary" href={`/download_photos/${ev.id}/`}>
                {t("Скачать фотографии и сканы документов")}
              </a>
              {card.archive && (
                <a className="btn-secondary" href={`/download_file/${ev.id}/`}>
                  {t("Скачать готовый архив")} {card.archive.name} ({card.archive.size_mb} MB, {formatDateTime(card.archive.modified)})
                </a>
              )}
              <Link className="btn-secondary" href={`/staff/${ev.id}/dashboard`}>
                {t("Дашборд и выгрузка")}
              </Link>
              <Link className="btn-secondary" href={`/staff/${ev.id}/review`}>
                {t("Очередь проверки")}
              </Link>
            </div>
          </section>

          <section className="card p-5" aria-labelledby="ev-reqs">
            <h2 id="ev-reqs" className="text-lg font-semibold">
              {t("Количество отправленных заявок:")} {card.requests.length}
            </h2>
            <ul className="divide-y divide-slate-100">{card.requests.map((r) => requestRow(r, true))}</ul>
            {card.active_requests.length > 0 && (
              <>
                <h3 className="mt-4 font-semibold">
                  {t("Количество неотправленных заявок:")} {card.active_requests.length}
                </h3>
                <ul className="divide-y divide-slate-100">{card.active_requests.map((r) => requestRow(r, false))}</ul>
              </>
            )}
          </section>

          <ConfirmButton
            className="btn-danger w-full"
            question={t("Удалить мероприятие «{name}» вместе со всеми заявками, участниками и файлами? Это действие необратимо.", {
              name: ev.name_rus,
            })}
            onConfirm={remove}
          >
            {t("Удалить мероприятие")}
          </ConfirmButton>
        </div>

        <div className="space-y-6">
          <section className="card p-5" aria-labelledby="ev-ops">
            <h2 id="ev-ops" className="mb-3 text-lg font-semibold">
              {t("Прикрепленные пользователи")} <span className="text-slate-400">({card.operators.length})</span>
            </h2>
            <ul className="divide-y divide-slate-100">
              {card.operators.map((o) => (
                <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <div>
                    <Link href={`/admin/operators/${o.id}`} className="font-medium text-brand-700 hover:underline">
                      {o.last_name} {o.first_name} {o.patronymic}
                    </Link>
                    <div className="text-xs text-slate-500">
                      {o.username}, {o.workplace} · {o.phone_number}
                    </div>
                  </div>
                  <ConfirmButton
                    className="btn-ghost px-2 py-1 text-xs text-red-700"
                    question={t("Открепить мероприятие от пользователя {name}?", { name: `${o.last_name} ${o.first_name}` })}
                    onConfirm={() => unbind(o.id)}
                  >
                    {t("Открепить")}
                  </ConfirmButton>
                </li>
              ))}
            </ul>
          </section>

          <section className="card p-5" aria-labelledby="ev-bind">
            <h2 id="ev-bind" className="mb-3 text-lg font-semibold">
              {t("Добавить участников аккредитации")}
            </h2>
            <select
              multiple
              size={Math.min(15, Math.max(5, card.other_operators.length))}
              className="input"
              aria-labelledby="ev-bind"
              value={selected}
              onChange={(e) => setSelected(Array.from(e.target.selectedOptions).map((o) => o.value))}
            >
              {card.other_operators.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.last_name} {o.first_name} {o.patronymic} {o.username}
                </option>
              ))}
            </select>
            <button type="button" className="btn-primary mt-3 w-full" disabled={!selected.length} onClick={bind}>
              {t("Добавить участников аккредитации")}
            </button>
          </section>

          <section className="card p-5" aria-labelledby="ev-newop">
            <h2 id="ev-newop" className="mb-3 text-lg font-semibold">
              {t("Новый оператор")}
            </h2>
            <OperatorCreateForm
              events={card.events}
              defaultEventId={ev.id}
              onDone={(text, ok) => {
                setNotice({ ok, text });
                load();
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            />
          </section>
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AdminOnly>
      <EventCard />
    </AdminOnly>
  );
}
