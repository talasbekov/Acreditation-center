"use client";

import { useCallback, useEffect, useState } from "react";
import { api, API_BASE, ApiException, getToken } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Badge, EmptyState, Modal, Spinner } from "@/components/ui";
import type { ExportItem } from "@/lib/types";

interface ExportParticipant {
  id: string;
  last_name: string;
  first_name: string;
  middle_name?: string;
  doc_number: string;
  citizenship: string;
}

export default function ExportsTab({ eventId }: { eventId: string }) {
  const toast = useToast();
  const [list, setList] = useState<ExportItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [execFor, setExecFor] = useState<ExportItem | null>(null);
  const [execParts, setExecParts] = useState<ExportParticipant[]>([]);
  const [denied, setDenied] = useState<Set<string>>(new Set());
  const [execLoading, setExecLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<{ data: ExportItem[] }>(`/events/${eventId}/exports`);
      setList(res.data || []);
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    load();
  }, [load]);

  const download = (id: string) => {
    const url = `${API_BASE}/exports/${id}/download`;
    fetch(url, { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `export-${id}.json`;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => toast.push("Ошибка скачивания", "error"));
  };

  const openExecute = async (ex: ExportItem) => {
    setExecFor(ex);
    setDenied(new Set());
    setExecLoading(true);
    try {
      const data = await api<{ participants: ExportParticipant[] }>(
        `/exports/${ex.id}/download`
      );
      setExecParts(data.participants || []);
    } catch {
      toast.push("Не удалось загрузить участников выгрузки", "error");
    } finally {
      setExecLoading(false);
    }
  };

  const toggleDeny = (id: string) => {
    setDenied((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const submitExecute = async () => {
    if (!execFor) return;
    setSubmitting(true);
    try {
      const res = await api<{ granted: number; denied: number }>(
        `/exports/${execFor.id}/execute`,
        { method: "POST", body: { denied_participant_ids: Array.from(denied) } }
      );
      toast.push(`Исполнено: ${res.granted} разрешено, ${res.denied} запрещено`);
      setExecFor(null);
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div>
      <p className="mb-4 text-sm text-slate-500">
        Выгрузки на проверку формируются на вкладке «Участники» — выберите участников
        и нажмите «Выгрузить на проверку».
      </p>

      {list.length === 0 ? (
        <EmptyState text="Выгрузок пока нет" />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Выгрузка</th>
                <th className="px-4 py-3">Участников</th>
                <th className="px-4 py-3">Создана</th>
                <th className="px-4 py-3">Статус</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.map((ex) => (
                <tr key={ex.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {ex.id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-3">{ex.participant_count}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {new Date(ex.created_at).toLocaleString("ru-RU")}
                    <div className="text-xs text-slate-400">{ex.created_by}</div>
                  </td>
                  <td className="px-4 py-3">
                    {ex.status === "executed" ? (
                      <div className="flex flex-col gap-1">
                        <Badge color="green">Исполнена</Badge>
                        <span className="text-xs text-slate-400">
                          ✓ {ex.granted} / ✗ {ex.denied}
                        </span>
                      </div>
                    ) : (
                      <Badge color="amber">Создана</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button onClick={() => download(ex.id)} className="btn-secondary text-xs">
                        ⬇ JSON
                      </button>
                      {ex.status !== "executed" && (
                        <button onClick={() => openExecute(ex)} className="btn-primary text-xs">
                          Исполнить
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={!!execFor}
        onClose={() => setExecFor(null)}
        title="Исполнить результат проверки"
        wide
      >
        {execLoading ? (
          <Spinner />
        ) : (
          <div>
            <p className="mb-4 text-sm text-slate-500">
              Отметьте участников, которым <b>доступ запрещён</b> (по файлу результата
              СГО). Остальным доступ будет разрешён.
            </p>
            <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-200">
              <table className="w-full text-sm">
                <tbody className="divide-y divide-slate-100">
                  {execParts.map((p) => (
                    <tr key={p.id} className={denied.has(p.id) ? "bg-red-50" : ""}>
                      <td className="px-4 py-2">
                        <label className="flex cursor-pointer items-center gap-3">
                          <input
                            type="checkbox"
                            checked={denied.has(p.id)}
                            onChange={() => toggleDeny(p.id)}
                          />
                          <span>
                            <span className="font-medium">
                              {p.last_name} {p.first_name} {p.middle_name}
                            </span>
                            <span className="ml-2 text-xs text-slate-400">
                              {p.citizenship} · {p.doc_number}
                            </span>
                          </span>
                        </label>
                      </td>
                      <td className="px-4 py-2 text-right">
                        {denied.has(p.id) ? (
                          <Badge color="red">Запрещён</Badge>
                        ) : (
                          <Badge color="green">Разрешён</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 flex items-center justify-between">
              <span className="text-sm text-slate-500">
                Запрещено: <b>{denied.size}</b> из {execParts.length}
              </span>
              <div className="flex gap-2">
                <button onClick={() => setExecFor(null)} className="btn-secondary">
                  Отмена
                </button>
                <button onClick={submitExecute} className="btn-primary" disabled={submitting}>
                  {submitting ? "…" : "Исполнить выгрузку"}
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
