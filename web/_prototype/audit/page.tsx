"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge, EmptyState, Spinner } from "@/components/ui";
import type { AuditEntry } from "@/lib/types";

const ACTION_LABELS: Record<string, string> = {
  "event.created": "Создано мероприятие",
  "event.updated": "Изменено мероприятие",
  "event.deleted": "Удалено мероприятие",
  "operator.created": "Создан оператор",
  "operator.password_reset": "Сброшен пароль",
  "participant.created": "Добавлен участник",
  "participant.updated": "Изменён участник",
  "participant.deleted": "Удалён участник",
  "participant.self_registered": "Саморегистрация",
  "export.created": "Создана выгрузка",
  "export.executed": "Исполнена выгрузка",
};

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actorType, setActorType] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<{ data: AuditEntry[] }>("/audit-log", {
        query: { actor_type: actorType, per_page: 200 },
      });
      setEntries(res.data || []);
    } finally {
      setLoading(false);
    }
  }, [actorType]);

  useEffect(() => {
    load();
  }, [load]);

  const actorColor = (t: string) =>
    t === "user" ? "blue" : t === "operator" ? "green" : "gray";

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Журнал аудита</h1>
        <select
          className="input max-w-[200px]"
          value={actorType}
          onChange={(e) => setActorType(e.target.value)}
        >
          <option value="">Все субъекты</option>
          <option value="user">Администраторы</option>
          <option value="operator">Операторы</option>
          <option value="system">Система</option>
        </select>
      </div>

      {loading ? (
        <Spinner />
      ) : entries.length === 0 ? (
        <EmptyState text="Записей аудита пока нет" />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Время</th>
                <th className="px-4 py-3">Субъект</th>
                <th className="px-4 py-3">Действие</th>
                <th className="px-4 py-3">Детали</th>
                <th className="px-4 py-3">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map((e) => (
                <tr key={e.id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                    {new Date(e.created_at).toLocaleString("ru-RU")}
                  </td>
                  <td className="px-4 py-3">
                    <Badge color={actorColor(e.actor_type) as "blue" | "green" | "gray"}>
                      {e.actor_name || e.actor_type}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-800">
                    {ACTION_LABELS[e.action] || e.action}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {e.details
                      ? Object.entries(e.details)
                          .map(([k, v]) => `${k}: ${v}`)
                          .join(", ")
                      : "—"}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">
                    {e.ip_address}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
