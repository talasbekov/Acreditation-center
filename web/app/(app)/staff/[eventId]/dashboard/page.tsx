"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiException, download, postLegacy } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { Dashboard } from "@/lib/types";
import Notice, { type NoticeValue } from "@/components/Notice";
import StaffShell from "@/components/staff/StaffShell";
import { Badge, PageHeader, Spinner, formatDateTime } from "@/components/ui";

/** «Дашборд и выгрузка» (`/dashboard/<event>/`): статусы, флаги, пакеты выгрузки. */
function DashboardPage({ eventId }: { eventId: string }) {
  const { t, err } = useLang();
  const [d, setD] = useState<Dashboard | null>(null);
  const [notice, setNotice] = useState<NoticeValue>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    const data = await api<Dashboard>(`/staff/events/${eventId}/dashboard/`);
    setD(data);
    return data;
  }, [eventId]);

  useEffect(() => {
    load().catch(() => setNotice({ ok: false, text: t("Не удалось подключиться к серверу") }));
  }, [load, t]);

  /**
   * «Скачать новые записи»: POST формирует пакет и отвечает 303 на адрес файла.
   * Файл берём отдельной ссылкой (браузер качает потоком и умеет докачку), а не в память.
   */
  const exportDelta = async (requestId: number) => {
    setBusy(requestId);
    setNotice(null);
    try {
      const before = d?.packages[0]?.package_id;
      const r = await postLegacy(`/export_delta/${eventId}/${requestId}/`);
      if (!r.redirected) {
        setNotice({ ok: r.status < 400, text: r.text });
        return;
      }
      const fresh = await load();
      const pkg = fresh.packages[0];
      if (pkg && pkg.package_id !== before) {
        window.location.href = `/export_package/${pkg.package_id}/download/`;
        setNotice({ ok: true, text: t("Пакет сформирован: {name}", { name: pkg.archive_name }) });
      }
    } catch {
      setNotice({ ok: false, text: t("Не удалось подключиться к серверу") });
    } finally {
      setBusy(null);
    }
  };

  /** Исполнение результата проверки СГО: файл JSON с denied_participant_ids. */
  const execute = async (packageId: string, file: File) => {
    const body = new FormData();
    body.set("result", file);
    try {
      const r = await api<{ allowed: number; denied: number }>(`/staff/packages/${packageId}/execute/`, { method: "POST", body });
      setNotice({ ok: true, text: t("Результат исполнен: доступ разрешён — {a}, запрещён — {d}", { a: r.allowed, d: r.denied }) });
      await load();
    } catch (e) {
      setNotice({ ok: false, text: e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу") });
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const acknowledge = async (packageId: string) => {
    const r = await postLegacy(`/export_package/${packageId}/acknowledge/`);
    if (!r.redirected) setNotice({ ok: false, text: r.text || t("Произошла ошибка. Повторите позже.") });
    await load();
  };

  if (!d) return notice ? <Notice value={notice} /> : <Spinner />;
  const ev = d.event;

  const stat = (num: number, badge: React.ReactNode, label: string, href?: string) => {
    const body = (
      <>
        <span className="block text-3xl font-bold text-slate-900">{num}</span>
        <span className="text-sm text-slate-600">
          {badge} {label}
        </span>
      </>
    );
    return href ? (
      <Link href={href} className="card block p-4 hover:border-brand-500">
        {body}
      </Link>
    ) : (
      <div className="card p-4">{body}</div>
    );
  };

  return (
    <div>
      <PageHeader title={t("Дашборд и выгрузка")} subtitle={`${ev.name_rus || ev.event_code} · ${t("всего участников")}: ${d.total}`} />
      <Notice value={notice} />

      <h2 className="mb-3 text-lg font-semibold">{t("Статусы участников")}</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {stat(d.ready, <Badge color="green">{t("Допущены")}</Badge>, t("готовы к выгрузке"))}
        {stat(d.review, <Badge color="amber">{t("На проверке")}</Badge>, t("открыть очередь →"), `/staff/${eventId}/review`)}
        {stat(d.draft, <Badge color="blue">{t("Черновики")}</Badge>, t("у операторов"))}
        {stat(d.exported, <Badge color="green">{t("Выгружены")}</Badge>, t("переданы в службу"))}
      </div>
      {d.access && (
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <span className="text-slate-500">{t("Результат проверки СГО")}:</span>
          <Badge color="green">{t("Доступ разрешён")}: {d.access.yes || 0}</Badge>
          <Badge color="red">{t("Доступ запрещён")}: {d.access.no || 0}</Badge>
          <Badge color="gray">{t("Не определён")}: {d.access.none || 0}</Badge>
          <Link href={`/staff/${eventId}/badges`} className="text-brand-700 hover:underline">
            {t("Бейджи")} →
          </Link>
        </div>
      )}
      {d.all_ready && (
        <p className="mt-4 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800">
          {t("Все {n} участников готовы к экспорту", { n: d.total })}
        </p>
      )}

      <h2 className="mb-3 mt-8 text-lg font-semibold">
        {t("Требуют внимания")}
        {d.flags_total ? ` (${d.flags_total})` : ""}
      </h2>
      <div className="grid gap-3 lg:grid-cols-3">
        {d.flags.map((f) => (
          <section key={f.key} className="card p-4" aria-labelledby={`flag-${f.key}`}>
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 id={`flag-${f.key}`} className="font-semibold">
                {t(f.label)}
              </h3>
              <Badge color={f.total ? "red" : "green"}>{f.total}</Badge>
            </div>
            {f.items.length ? (
              <ul className="space-y-1 text-sm">
                {f.items.map((a) => (
                  <li key={a.id}>
                    <Link href={`/attendees/${a.id}/edit`} className="text-brand-700 hover:underline">
                      {a.name || a.id}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">{t("Нет записей с этой проблемой.")}</p>
            )}
            {f.overflow && <p className="mt-2 text-xs text-slate-500">{t("Показаны первые {n} — есть ещё. Уточните выборку.", { n: f.shown })}</p>}
          </section>
        ))}
      </div>

      <h2 className="mb-1 mt-8 text-lg font-semibold">{t("Выгрузка новых записей")}</h2>
      <p className="mb-3 text-sm text-slate-500">{t("Пакет включает допущенных участников заявки, которых ещё не выгружали.")}</p>
      {d.categories.length ? (
        <ul className="space-y-2">
          {d.categories.map((c) => (
            <li key={c.id} className="card flex flex-wrap items-center justify-between gap-2 p-3">
              <span className="font-medium">
                {t("Заявка")} {c.name}
              </span>
              <button type="button" className="btn-primary" disabled={busy !== null} onClick={() => exportDelta(c.id)}>
                {busy === c.id ? t("Загрузка…") : t("Скачать новые записи")}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">{t("Нет категорий (заявок) в этом мероприятии.")}</p>
      )}

      <h2 className="mb-3 mt-8 text-lg font-semibold">{t("Пакеты выгрузки")}</h2>
      {d.packages.length ? (
        <ul className="space-y-3">
          {d.packages.map((p) => (
            <li key={p.package_id} className="card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold">{p.category ? `${t("Заявка")} ${p.category}` : t("Все категории")}</h3>
                {p.acknowledged_at ? (
                  <Badge color="green">{t("Приём подтверждён")}</Badge>
                ) : (
                  <Badge color="amber">{t("Приём не подтверждён")}</Badge>
                )}
              </div>
              <p className="mt-1 text-sm text-slate-500">
                {formatDateTime(p.exported_before)} · {t("участников")}: {p.attendee_count}
              </p>
              <p className="text-xs text-slate-500">
                {t("Пакет")} <code>{p.package_id}</code>
                {p.archive_name && (
                  <>
                    {" "}
                    · <code>{p.archive_name}</code>
                  </>
                )}
              </p>
              {p.acknowledged_at && (
                <p className="text-xs text-slate-500">
                  {t("Получатель подтвердил приём")} {formatDateTime(p.acknowledged_at)}
                  {p.acknowledged_by ? ` (${t("отметил")} ${p.acknowledged_by})` : ""}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                {p.can_redownload ? (
                  <a className="btn-secondary" href={`/export_package/${p.package_id}/download/`} download>
                    {t("Скачать повторно")}
                  </a>
                ) : (
                  <p className="text-xs text-slate-500">{t("Повторная выдача недоступна: пакет сформирован до записи состава")}</p>
                )}
                {!p.acknowledged_at && (
                  <button type="button" className="btn-primary" onClick={() => acknowledge(p.package_id)}>
                    {t("Получатель подтвердил приём")}
                  </button>
                )}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
                {p.executed_at ? (
                  <Badge color="green">
                    {t("Результат СГО исполнен")} {formatDateTime(p.executed_at)} · {t("запрещено")}: {p.denied_count}
                  </Badge>
                ) : (
                  <Badge color="amber">{t("Результат СГО не исполнен")}</Badge>
                )}
                <label className="btn-secondary cursor-pointer">
                  {p.executed_at ? t("Исполнить повторно…") : t("Исполнить результат…")}
                  <input
                    type="file"
                    accept=".json,application/json"
                    className="sr-only"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      e.target.value = "";
                      if (f) execute(p.package_id, f);
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="btn-ghost text-xs"
                  onClick={() => download(`/staff/packages/${p.package_id}/result-template/`, `result_${p.package_id}.json`)}
                >
                  {t("Заготовка файла результата")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">{t("Выгрузок по этому мероприятию ещё не было.")}</p>
      )}
    </div>
  );
}

export default function Page() {
  const { eventId } = useParams<{ eventId: string }>();
  return (
    <StaffShell eventId={eventId}>
      <DashboardPage eventId={eventId} />
    </StaffShell>
  );
}
