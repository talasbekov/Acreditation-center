"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import type { Cabinet, CabinetRequest, RequestDetail } from "@/lib/types";
import { Badge, ConfirmButton, ErrorBox, PageHeader, Spinner, formatDate } from "@/components/ui";

/** Подпись статуса заявки — как в `gov2.html`. */
function RequestStatus({ status }: { status: string }) {
  const { t } = useLang();
  if (status === "Active") return <Badge color="blue">{t("Создано")}</Badge>;
  if (status === "Checking") return <Badge color="amber">{t("На предпросмотре")}</Badge>;
  if (status === "Sent") return <Badge color="amber">{t("Отправлено")}</Badge>;
  if (status === "Exported") return <Badge color="green">{t("Принято")}</Badge>;
  return <Badge color="gray">{t("Неизвестен")}</Badge>;
}

/** Кабинет оператора (`/application/`): мероприятия и заявки по каждому из них. */
export default function CabinetPage() {
  const { me } = useAuth();
  const { t, name, err, lang } = useLang();
  const router = useRouter();
  const [data, setData] = useState<Cabinet | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api<Cabinet>("/cabinet/", { query: { lang } }));
    } catch (e) {
      setError(e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу"));
    }
  }, [lang, err, t]);

  useEffect(() => {
    load();
  }, [load]);

  const createRequest = async (eventId: number) => {
    setBusy(eventId);
    setError("");
    try {
      const req = await api<RequestDetail>("/requests/", { method: "POST", body: { event: eventId } });
      router.push(`/requests/${req.id}`);
    } catch (e) {
      setError(e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу"));
      setBusy(null);
    }
  };

  const deleteRequest = async (r: CabinetRequest) => {
    try {
      await api(`/requests/${r.id}/`, { method: "DELETE" });
      await load();
    } catch (e) {
      setError(e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу"));
    }
  };

  if (!data && !error) return <Spinner />;
  const fullName = me ? [me.first_name, me.last_name].filter(Boolean).join(" ") || me.username : "";

  return (
    <div>
      <PageHeader
        title={
          data && data.events.length
            ? t("Список мероприятий, на которые Вам был предоставлен доступ")
            : t("Нет предстоящих активных мероприятий")
        }
        subtitle={t("Добро пожаловать, {name}", { name: fullName })}
      />
      <ErrorBox text={error} />
      <div className="space-y-4">
        {data?.events.map((ev) => {
          const reqs = data.requests.filter((r) => r.event_id === ev.id);
          return (
            <section key={ev.id} className="card p-5" aria-labelledby={`event-${ev.id}`}>
              <h2 id={`event-${ev.id}`} className="text-lg font-semibold text-slate-900">
                {t("Мероприятие:")} {name(ev)}
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                {t("Город:")} {ev.city_name || "—"} · {t("Дата:")} {formatDate(ev.date_start)} – {formatDate(ev.date_end)}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className="btn-primary" disabled={busy === ev.id} onClick={() => createRequest(ev.id)}>
                  {t("+ Создать новый список участников (заявку) для этого мероприятия")}
                </button>
                {me && (me.role === "superoperator" || me.role === "superuser") && (
                  <>
                    <Link className="btn-secondary" href={`/staff/${ev.id}/review`}>
                      {t("Очередь проверки")}
                    </Link>
                    <Link className="btn-secondary" href={`/staff/${ev.id}/dashboard`}>
                      {t("Дашборд и выгрузка")}
                    </Link>
                  </>
                )}
              </div>
              {reqs.length > 0 && (
                <ul className="mt-4 divide-y divide-slate-100 border-t border-slate-100">
                  {reqs.map((r) => (
                    <li key={r.id} className="flex flex-wrap items-center gap-3 py-3">
                      <span className="font-medium text-slate-800">
                        {t("Номер заявки:")} {r.name}
                      </span>
                      <RequestStatus status={r.status} />
                      {r.returned_count > 0 && <Badge color="red">{t("Возвращено на доработку: {n}", { n: r.returned_count })}</Badge>}
                      <span className="ml-auto flex flex-wrap items-center gap-2">
                        <Link href={`/requests/${r.id}`} className={r.status === "Active" ? "btn-primary" : "btn-secondary"}>
                          {r.status === "Active" ? t("Редактировать список участников") : t("Посмотреть список участников")}
                        </Link>
                        {r.status === "Active" && (
                          <ConfirmButton
                            className="btn-ghost text-red-700"
                            question={t("Удалить заявку {name} вместе с участниками?", { name: r.name })}
                            onConfirm={() => deleteRequest(r)}
                          >
                            {t("удалить список")}
                          </ConfirmButton>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}
