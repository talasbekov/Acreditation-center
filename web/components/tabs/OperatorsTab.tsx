"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Badge, EmptyState, Spinner } from "@/components/ui";
import type { Operator } from "@/lib/types";

export default function OperatorsTab({ eventId }: { eventId: string }) {
  const toast = useToast();
  const [operators, setOperators] = useState<Operator[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<{ data: Operator[] }>("/operators");
      setOperators(res.data || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const attached = operators.filter((o) => o.events?.includes(eventId));
  const available = operators.filter((o) => !o.events?.includes(eventId));

  const attach = async () => {
    if (!selected) return;
    try {
      await api(`/events/${eventId}/operators`, {
        method: "POST",
        body: { operator_id: selected },
      });
      toast.push("Оператор привязан");
      setSelected("");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  const detach = async (o: Operator) => {
    if (!confirm(`Отвязать оператора ${o.full_name} от мероприятия?`)) return;
    try {
      await api(`/events/${eventId}/operators/${o.id}`, { method: "DELETE" });
      toast.push("Оператор отвязан");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  if (loading) return <Spinner />;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          className="input max-w-sm"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          <option value="">Выберите оператора для привязки…</option>
          {available.map((o) => (
            <option key={o.id} value={o.id}>
              {o.full_name} ({o.login}) — {o.organization}
            </option>
          ))}
        </select>
        <button onClick={attach} className="btn-primary" disabled={!selected}>
          Привязать
        </button>
      </div>

      {attached.length === 0 ? (
        <EmptyState text="К мероприятию не привязан ни один оператор" />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Оператор</th>
                <th className="px-4 py-3">Организация</th>
                <th className="px-4 py-3">Роль</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {attached.map((o) => (
                <tr key={o.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{o.full_name}</div>
                    <div className="text-xs text-slate-400">
                      {o.login} · {o.phone}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{o.organization}</td>
                  <td className="px-4 py-3">
                    <Badge color={o.role === "superoperator" ? "blue" : "gray"}>
                      {o.role === "superoperator" ? "Супероператор" : "Оператор"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => detach(o)} className="btn-ghost text-xs text-red-600">
                      Отвязать
                    </button>
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
