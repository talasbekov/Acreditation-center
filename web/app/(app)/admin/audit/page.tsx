"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import AdminOnly from "@/components/admin/AdminOnly";
import { ErrorBox, PageHeader, Spinner, formatDateTime } from "@/components/ui";

interface Row {
  id: number;
  created_at: string;
  actor: string;
  role: string;
  action: string;
  obj_type: string;
  obj_id: string;
  ip: string | null;
  extra: Record<string, unknown>;
}

interface Data {
  count: number;
  page: number;
  page_size: number;
  results: Row[];
  actions: string[];
}

/** Журнал аудита: кто, что и когда сделал (вход, правки, выгрузки, удаления, бейджи). */
function AuditPage() {
  const { t } = useLang();
  const [filters, setFilters] = useState({ action: "", actor: "", obj_type: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await api<Data>("/admin/audit-log/", { query: { ...filters, page } }));
      setError("");
    } catch (e) {
      setError(e instanceof ApiException ? String(e.problem.detail || e.message) : t("Не удалось подключиться к серверу"));
    }
  }, [filters, page, t]);

  useEffect(() => {
    load();
  }, [load]);

  const set = (k: keyof typeof filters) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setPage(1);
    setFilters((f) => ({ ...f, [k]: e.target.value }));
  };
  const pages = data ? Math.max(1, Math.ceil(data.count / data.page_size)) : 1;

  return (
    <div>
      <PageHeader title={t("Журнал аудита")} subtitle={data ? `${t("Записей")}: ${data.count}` : undefined} />
      <ErrorBox text={error} />
      <div className="card mb-4 grid gap-3 p-4 sm:grid-cols-5">
        <label>
          <span className="label">{t("Действие")}</span>
          <select className="input" value={filters.action} onChange={set("action")}>
            <option value="">{t("Все")}</option>
            {data?.actions.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="label">{t("Пользователь")}</span>
          <input className="input" value={filters.actor} onChange={set("actor")} />
        </label>
        <label>
          <span className="label">{t("Объект")}</span>
          <input className="input" value={filters.obj_type} onChange={set("obj_type")} placeholder="Attendee" />
        </label>
        <label>
          <span className="label">{t("С")}</span>
          <input className="input" type="date" value={filters.date_from} onChange={set("date_from")} />
        </label>
        <label>
          <span className="label">{t("По")}</span>
          <input className="input" type="date" value={filters.date_to} onChange={set("date_to")} />
        </label>
      </div>
      {!data ? (
        <Spinner />
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="p-3">{t("Когда")}</th>
                <th className="p-3">{t("Кто")}</th>
                <th className="p-3">{t("Действие")}</th>
                <th className="p-3">{t("Объект")}</th>
                <th className="p-3">IP</th>
                <th className="p-3">{t("Подробности")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.results.map((r) => (
                <tr key={r.id} className="align-top">
                  <td className="whitespace-nowrap p-3">{formatDateTime(r.created_at)}</td>
                  <td className="p-3">
                    {r.actor} <span className="text-xs text-slate-500">({r.role})</span>
                  </td>
                  <td className="p-3 font-mono text-xs">{r.action}</td>
                  <td className="p-3 text-xs">
                    {r.obj_type} {r.obj_id}
                  </td>
                  <td className="p-3 text-xs">{r.ip}</td>
                  <td className="max-w-xs p-3 font-mono text-xs text-slate-600">
                    {Object.keys(r.extra || {}).length ? JSON.stringify(r.extra) : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-3 text-sm">
            <button type="button" className="btn-secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              ←
            </button>
            <span>
              {page} / {pages}
            </span>
            <button type="button" className="btn-secondary" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
              →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <AdminOnly>
      <AuditPage />
    </AdminOnly>
  );
}
