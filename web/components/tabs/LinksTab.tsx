"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Badge, EmptyState, Field, Modal, Spinner } from "@/components/ui";
import type { RegistrationLink } from "@/lib/types";

export default function LinksTab({ eventId }: { eventId: string }) {
  const toast = useToast();
  const [links, setLinks] = useState<RegistrationLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [linkType, setLinkType] = useState<"single" | "multi">("single");
  const [count, setCount] = useState(5);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<{ data: RegistrationLink[] }>(
        `/events/${eventId}/registration-links`
      );
      setLinks(res.data || []);
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api(`/events/${eventId}/registration-links`, {
        method: "POST",
        body: linkType === "single" ? { link_type: "single", count } : { link_type: "multi" },
      });
      toast.push(linkType === "single" ? `Создано ссылок: ${count}` : "Ссылка создана");
      setOpen(false);
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const deactivate = async (l: RegistrationLink) => {
    if (!confirm("Деактивировать ссылку?")) return;
    try {
      await api(`/registration-links/${l.id}`, { method: "DELETE" });
      toast.push("Ссылка деактивирована");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  const copy = (url: string) => {
    navigator.clipboard.writeText(url);
    toast.push("Ссылка скопирована", "info");
  };

  if (loading) return <Spinner />;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Одноразовые — для одного участника каждая. Многоразовая — открытая регистрация.
        </p>
        <button onClick={() => setOpen(true)} className="btn-primary">
          + Создать ссылки
        </button>
      </div>

      {links.length === 0 ? (
        <EmptyState text="Ссылок саморегистрации пока нет" />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Ссылка</th>
                <th className="px-4 py-3">Тип</th>
                <th className="px-4 py-3">Статус</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {links.map((l) => (
                <tr key={l.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <code className="text-xs text-slate-500">{l.url}</code>
                  </td>
                  <td className="px-4 py-3">
                    <Badge color={l.link_type === "multi" ? "blue" : "gray"}>
                      {l.link_type === "multi" ? "Многоразовая" : "Одноразовая"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {!l.is_active ? (
                      <Badge color="red">Деактивирована</Badge>
                    ) : l.is_used ? (
                      <Badge color="amber">Использована</Badge>
                    ) : (
                      <Badge color="green">Активна</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button onClick={() => copy(l.url)} className="btn-ghost text-xs">
                        Копировать
                      </button>
                      {l.is_active && (
                        <button onClick={() => deactivate(l)} className="btn-ghost text-xs text-red-600">
                          Деактивировать
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

      <Modal open={open} onClose={() => setOpen(false)} title="Создать ссылки">
        <form onSubmit={create} className="space-y-4">
          <Field label="Тип ссылки">
            <select
              className="input"
              value={linkType}
              onChange={(e) => setLinkType(e.target.value as "single" | "multi")}
            >
              <option value="single">Одноразовые (по числу участников)</option>
              <option value="multi">Многоразовая (открытая регистрация)</option>
            </select>
          </Field>
          {linkType === "single" && (
            <Field label="Количество ссылок">
              <input
                type="number"
                min={1}
                max={500}
                className="input"
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
              />
            </Field>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setOpen(false)} className="btn-secondary">
              Отмена
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "…" : "Создать"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
