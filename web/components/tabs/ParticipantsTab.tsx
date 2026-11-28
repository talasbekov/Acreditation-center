"use client";

import { useCallback, useEffect, useState } from "react";
import { api, API_BASE, ApiException, apiBlob, downloadBlob, getToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/toast";
import { Badge, EmptyState, Modal, Spinner } from "@/components/ui";
import ParticipantForm, {
  participantToPayload,
  type ParticipantPayload,
} from "@/components/ParticipantForm";
import type { Participant } from "@/lib/types";

function accessBadge(p: Participant) {
  if (p.access_status === "yes") return <Badge color="green">Доступ разрешён</Badge>;
  if (p.access_status === "no") return <Badge color="red">Доступ запрещён</Badge>;
  return <Badge color="gray">Не определён</Badge>;
}

function photoSrc(url: string) {
  // backend returns absolute path under /api/v1; API_BASE already includes /api/v1
  return API_BASE.replace(/\/api\/v1$/, "") + url + (getToken() ? "" : "");
}

export default function ParticipantsTab({
  eventId,
  onChanged,
}: {
  eventId: string;
  onChanged: () => void;
}) {
  const { isAdmin } = useAuth();
  const toast = useToast();
  const [list, setList] = useState<Participant[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [fExported, setFExported] = useState("");
  const [fAccess, setFAccess] = useState("");
  const [fBadge, setFBadge] = useState("");

  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState<Participant | null>(null);
  const [viewing, setViewing] = useState<Participant | null>(null);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<{ data: Participant[] }>(
        `/events/${eventId}/participants`,
        {
          query: {
            search,
            is_exported: fExported,
            access_status: fAccess,
            badge_printed: fBadge,
            per_page: 200,
          },
        }
      );
      setList(res.data || []);
    } catch {
      toast.push("Не удалось загрузить участников", "error");
    } finally {
      setLoading(false);
    }
  }, [eventId, search, fExported, fAccess, fBadge, toast]);

  useEffect(() => {
    const id = setTimeout(load, 250);
    return () => clearTimeout(id);
  }, [load]);

  const refresh = () => {
    load();
    onChanged();
  };

  const create = async (payload: ParticipantPayload) => {
    await api(`/events/${eventId}/participants`, { method: "POST", body: payload });
    toast.push("Участник добавлен");
    setAddOpen(false);
    refresh();
  };

  const update = async (payload: ParticipantPayload) => {
    if (!editing) return;
    await api(`/events/${eventId}/participants/${editing.id}`, {
      method: "PUT",
      body: payload,
    });
    toast.push("Участник обновлён");
    setEditing(null);
    refresh();
  };

  const remove = async (p: Participant) => {
    if (!confirm(`Удалить участника ${p.last_name} ${p.first_name}?`)) return;
    try {
      await api(`/events/${eventId}/participants/${p.id}`, { method: "DELETE" });
      toast.push("Участник удалён");
      refresh();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  // Печать одного бейджа — синхронно, без фоновой задачи (Процесс 12).
  const printBadge = async (p: Participant) => {
    try {
      const blob = await apiBlob(`/events/${eventId}/participants/${p.id}/badge.pdf`);
      downloadBlob(blob, `badge-${p.last_name}-${p.id.slice(0, 8)}.pdf`);
      toast.push("Бейдж сформирован");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectableIds = list.filter((p) => !p.is_exported).map((p) => p.id);
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selected.has(id));

  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(selectableIds));
  };

  const doExport = async () => {
    if (selected.size === 0) return;
    if (!confirm(`Выгрузить на проверку ${selected.size} участников?`)) return;
    setExporting(true);
    try {
      await api(`/events/${eventId}/exports`, {
        method: "POST",
        body: { participant_ids: Array.from(selected) },
      });
      toast.push(`Создана выгрузка: ${selected.size} участников`);
      setSelected(new Set());
      refresh();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          className="input max-w-xs"
          placeholder="Поиск: ФИО, ИИН, документ…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="input max-w-[180px]" value={fExported} onChange={(e) => setFExported(e.target.value)}>
          <option value="">Все (выгрузка)</option>
          <option value="false">Не выгружены</option>
          <option value="true">Выгружены</option>
        </select>
        <select className="input max-w-[180px]" value={fAccess} onChange={(e) => setFAccess(e.target.value)}>
          <option value="">Все (доступ)</option>
          <option value="none">Не определён</option>
          <option value="yes">Разрешён</option>
          <option value="no">Запрещён</option>
        </select>
        {isAdmin && (
          <select className="input max-w-[180px]" value={fBadge} onChange={(e) => setFBadge(e.target.value)}>
            <option value="">Все (бейдж)</option>
            <option value="false">Бейдж не печатался</option>
            <option value="true">Бейдж напечатан</option>
          </select>
        )}
        <div className="ml-auto flex gap-2">
          {isAdmin && selected.size > 0 && (
            <button onClick={doExport} className="btn-primary" disabled={exporting}>
              ⬆ Выгрузить на проверку ({selected.size})
            </button>
          )}
          {!isAdmin && (
            <button onClick={() => setAddOpen(true)} className="btn-primary">
              + Добавить участника
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <Spinner />
      ) : list.length === 0 ? (
        <EmptyState text="Участников пока нет" />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  {isAdmin && (
                    <th className="w-10 px-4 py-3">
                      <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                    </th>
                  )}
                  <th className="px-4 py-3">Участник</th>
                  <th className="px-4 py-3">Документ</th>
                  <th className="px-4 py-3">Гражданство</th>
                  <th className="px-4 py-3">Источник</th>
                  <th className="px-4 py-3">Статус</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {list.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    {isAdmin && (
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          disabled={p.is_exported}
                          checked={selected.has(p.id)}
                          onChange={() => toggleSelect(p.id)}
                        />
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <button onClick={() => setViewing(p)} className="flex items-center gap-3 text-left">
                        <img
                          src={photoSrc(p.photo_url)}
                          alt=""
                          className="h-10 w-8 rounded object-cover"
                        />
                        <div>
                          <div className="font-medium text-slate-900">
                            {p.last_name} {p.first_name} {p.middle_name}
                          </div>
                          <div className="text-xs text-slate-400">
                            {p.birth_date} · {p.position || "—"}
                          </div>
                        </div>
                      </button>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      <div className="capitalize">{p.doc_type}</div>
                      <div className="text-xs text-slate-400">
                        {p.doc_series} {p.doc_number}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{p.citizenship}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-500">
                        {p.source === "self" ? "Саморег." : p.source === "api" ? "API" : "Оператор"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1">
                        {p.is_exported ? (
                          <Badge color="blue">Выгружен</Badge>
                        ) : (
                          <Badge color="gray">Не выгружен</Badge>
                        )}
                        {accessBadge(p)}
                        {p.badge_printed_at && <Badge color="blue">Бейдж напечатан</Badge>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {isAdmin && p.access_status === "yes" && (
                        <button
                          onClick={() => printBadge(p)}
                          className="btn-secondary text-xs"
                          title={
                            p.badge_printed_at
                              ? "Перепечатать бейдж"
                              : "Скачать бейдж одной страницей"
                          }
                        >
                          🖨 Бейдж
                        </button>
                      )}
                      {!isAdmin && !p.is_exported && (
                        <div className="flex justify-end gap-1">
                          <button onClick={() => setEditing(p)} className="btn-ghost px-2 py-1 text-xs">
                            ✏️
                          </button>
                          <button onClick={() => remove(p)} className="btn-ghost px-2 py-1 text-xs text-red-600">
                            🗑
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add */}
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Новый участник" wide>
        <ParticipantForm
          eventId={eventId}
          submitLabel="Добавить"
          onSubmit={create}
          onCancel={() => setAddOpen(false)}
        />
      </Modal>

      {/* Edit */}
      <Modal open={!!editing} onClose={() => setEditing(null)} title="Редактировать участника" wide>
        {editing && (
          <ParticipantForm
            eventId={eventId}
            initial={participantToPayload(editing)}
            submitLabel="Сохранить"
            onSubmit={update}
            onCancel={() => setEditing(null)}
          />
        )}
      </Modal>

      {/* View */}
      <Modal open={!!viewing} onClose={() => setViewing(null)} title="Карточка участника" wide>
        {viewing && (
          <div className="grid gap-6 sm:grid-cols-[200px_1fr]">
            <div className="space-y-3">
              <img src={photoSrc(viewing.photo_url)} alt="" className="w-full rounded-lg border border-slate-200" />
              <img src={photoSrc(viewing.doc_scan_url)} alt="" className="w-full rounded-lg border border-slate-200" />
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <Info label="ФИО" value={`${viewing.last_name} ${viewing.first_name} ${viewing.middle_name || ""}`} />
              <Info label="Транслит" value={`${viewing.last_name_en || "—"} ${viewing.first_name_en || ""}`} />
              <Info label="ИИН" value={viewing.iin || "—"} />
              <Info label="Дата рождения" value={viewing.birth_date} />
              <Info label="Пол" value={viewing.gender === "male" ? "Мужской" : "Женский"} />
              <Info label="Гражданство" value={viewing.citizenship} />
              <Info label="Должность" value={viewing.position || "—"} />
              <Info label="Документ" value={`${viewing.doc_type} ${viewing.doc_series || ""} ${viewing.doc_number}`} />
              <Info label="Выдан" value={viewing.doc_issued_date} />
              <Info label="Действ. до" value={viewing.doc_expiry_date} />
              <Info label="Объекты" value={viewing.visit_objects || "—"} />
              <Info label="Категория" value={viewing.category || "—"} />
              <div className="col-span-2 flex gap-2 pt-2">
                {viewing.is_exported ? <Badge color="blue">Выгружен</Badge> : <Badge color="gray">Не выгружен</Badge>}
                {accessBadge(viewing)}
              </div>
            </dl>
          </div>
        )}
      </Modal>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase text-slate-400">{label}</dt>
      <dd className="font-medium text-slate-800">{value}</dd>
    </div>
  );
}
