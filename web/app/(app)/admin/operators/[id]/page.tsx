"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { setFlash } from "@/lib/flash";
import { useLang } from "@/lib/i18n";
import type { AdminOperatorCard } from "@/lib/types";
import AdminOnly from "@/components/admin/AdminOnly";
import Notice, { type NoticeValue } from "@/components/Notice";
import { Badge, ConfirmButton, PageHeader, Spinner, formatDate, formatDateTime } from "@/components/ui";

interface AccessEvent {
  event_type: string;
  timestamp: string;
  actor?: string | null;
  ip?: string | null;
}

interface RegistryDetail {
  inactivity_warning?: boolean;
  last_login?: string | null;
  access_events?: AccessEvent[];
}

const ACCESS_LABEL: Record<string, string> = {
  created: "Создан",
  login: "Вход",
  password_changed: "Смена пароля",
  deactivated: "Деактивирован",
  reactivated: "Активирован снова",
};

/** Карточка оператора (`/show_operator/<id>/`) + история доступа и деактивация. */
function OperatorCard() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { t, name } = useLang();
  const [card, setCard] = useState<AdminOperatorCard | null>(null);
  const [registry, setRegistry] = useState<RegistryDetail | null>(null);
  const [notice, setNotice] = useState<NoticeValue>(null);

  const load = useCallback(async () => {
    setCard(await api<AdminOperatorCard>(`/admin/operators/${id}/`));
    try {
      setRegistry(await api<RegistryDetail>(`/operators/${id}/`));
    } catch {
      setRegistry(null);
    }
  }, [id]);

  useEffect(() => {
    load().catch(() => setNotice({ ok: false, text: t("Оператор не найден") }));
  }, [load, t]);

  const fail = (e: unknown) =>
    setNotice({
      ok: false,
      text: e instanceof ApiException ? String(e.problem.message || e.problem.detail || e.message) : t("Не удалось подключиться к серверу"),
    });

  const newPassword = async () => {
    try {
      const r = await api<{ message: string }>(`/admin/operators/${id}/new-password/`, { method: "POST" });
      setNotice({ ok: true, text: r.message });
    } catch (e) {
      fail(e);
    }
  };

  const toggleActive = async (active: boolean) => {
    try {
      await api(`/operators/${id}/${active ? "reactivate" : "deactivate"}/`, { method: "POST" });
      setNotice({ ok: true, text: active ? t("Учётная запись активирована") : t("Учётная запись деактивирована") });
      await load();
    } catch (e) {
      fail(e);
    }
  };

  const remove = async () => {
    try {
      const r = await api<{ message: string }>(`/admin/operators/${id}/`, { method: "DELETE" });
      setFlash(r.message);
      router.push("/admin/operators");
    } catch (e) {
      fail(e);
    }
  };

  if (!card) return notice ? <Notice value={notice} /> : <Spinner />;
  const o = card.operator;

  return (
    <div>
      <PageHeader
        title={`${o.last_name} ${o.first_name} ${o.patronymic}`}
        subtitle={`${o.username} · ${o.workplace}`}
        back={{ href: "/admin/operators", label: t("Пользователи") }}
      />
      <Notice value={notice} />
      {registry?.inactivity_warning && (
        <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{t("Оператор давно не входил в систему")}</p>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <section className="card p-5" aria-labelledby="op-info">
            <h2 id="op-info" className="mb-3 text-lg font-semibold">
              {t("Оператор")}
            </h2>
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
              <dt className="text-slate-500">Email</dt>
              <dd>{o.email}</dd>
              <dt className="text-slate-500">{t("Контактные данные")}</dt>
              <dd>{o.phone_number}</dd>
              <dt className="text-slate-500">{t("Роль")}</dt>
              <dd>{t(o.role === "superoperator" ? "Супероператор" : "Оператор")}</dd>
              <dt className="text-slate-500">{t("Состояние")}</dt>
              <dd>{o.is_active ? <Badge color="green">{t("Активен")}</Badge> : <Badge color="red">{t("Деактивирован")}</Badge>}</dd>
            </dl>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" className="btn-secondary" onClick={newPassword}>
                {t("Отправить ссылку для установки пароля")}
              </button>
              {o.is_active ? (
                <ConfirmButton className="btn-secondary" question={t("Деактивировать учётную запись? Все сеансы оператора будут закрыты.")} onConfirm={() => toggleActive(false)}>
                  {t("Деактивировать")}
                </ConfirmButton>
              ) : (
                <button type="button" className="btn-secondary" onClick={() => toggleActive(true)}>
                  {t("Активировать")}
                </button>
              )}
              <ConfirmButton
                question={t("Удалить оператора {name}? Его заявки и участники будут удалены. Это действие необратимо.", {
                  name: `${o.last_name} ${o.first_name}`,
                })}
                onConfirm={remove}
              >
                {t("Удалить")}
              </ConfirmButton>
            </div>
          </section>

          <section className="card p-5" aria-labelledby="op-events">
            <h2 id="op-events" className="mb-3 text-lg font-semibold">
              {t("Мероприятия")}
            </h2>
            <ul className="divide-y divide-slate-100">
              {card.events.map((ev) => (
                <li key={ev.id} className="py-2">
                  <Link href={`/admin/events/${ev.id}`} className="font-medium text-brand-700 hover:underline">
                    {name(ev)}
                  </Link>
                  <div className="text-xs text-slate-500">
                    {formatDate(ev.date_start)} – {formatDate(ev.date_end)}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="space-y-6">
          <section className="card p-5" aria-labelledby="op-reqs">
            <h2 id="op-reqs" className="mb-3 text-lg font-semibold">
              {t("Заявки")} <span className="text-slate-400">({card.requests.length})</span>
            </h2>
            <ul className="divide-y divide-slate-100">
              {card.requests.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center gap-2 py-2">
                  <Link href={`/requests/${r.id}`} className="font-medium text-brand-700 hover:underline">
                    {r.name}
                  </Link>
                  <Badge color="gray">{r.status}</Badge>
                  <span className="text-xs text-slate-500">{formatDateTime(r.date_created)}</span>
                </li>
              ))}
            </ul>
          </section>

          {registry?.access_events && registry.access_events.length > 0 && (
            <section className="card p-5" aria-labelledby="op-access">
              <h2 id="op-access" className="mb-3 text-lg font-semibold">
                {t("История доступа")}
              </h2>
              <ul className="divide-y divide-slate-100 text-sm">
                {registry.access_events.map((a, i) => (
                  <li key={i} className="flex justify-between gap-2 py-1.5">
                    <span>{t(ACCESS_LABEL[a.event_type] || a.event_type)}</span>
                    <span className="text-slate-500">{formatDateTime(a.timestamp)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AdminOnly>
      <OperatorCard />
    </AdminOnly>
  );
}
