"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Badge, EmptyState, Field, Modal, Spinner } from "@/components/ui";
import type { ApiToken } from "@/lib/types";

export default function TokensTab({ eventId }: { eventId: string }) {
  const toast = useToast();
  const [tokens, setTokens] = useState<ApiToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<{ data: ApiToken[] }>(`/events/${eventId}/api-tokens`);
      setTokens(res.data || []);
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
      const res = await api<{ token: string }>(`/events/${eventId}/api-tokens`, {
        method: "POST",
        body: { name },
      });
      setCreated(res.token);
      setName("");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const revoke = async (t: ApiToken) => {
    if (!confirm(`Отозвать токен «${t.name}»?`)) return;
    try {
      await api(`/api-tokens/${t.id}`, { method: "DELETE" });
      toast.push("Токен отозван");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  const closeModal = () => {
    setOpen(false);
    setCreated(null);
  };

  if (loading) return <Spinner />;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Bearer-токены для подключения сторонней системы регистрации участников.
        </p>
        <button onClick={() => setOpen(true)} className="btn-primary">
          + Создать токен
        </button>
      </div>

      {tokens.length === 0 ? (
        <EmptyState text="API-токенов пока нет" />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Название</th>
                <th className="px-4 py-3">Токен</th>
                <th className="px-4 py-3">Статус</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {tokens.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{t.name}</td>
                  <td className="px-4 py-3">
                    <code className="text-xs text-slate-500">{t.token_mask}</code>
                  </td>
                  <td className="px-4 py-3">
                    {t.is_active ? <Badge color="green">Активен</Badge> : <Badge color="gray">Отозван</Badge>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => revoke(t)} className="btn-ghost text-xs text-red-600">
                      Отозвать
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={open} onClose={closeModal} title="API-токен">
        {created ? (
          <div className="space-y-4">
            <div className="rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
              Сохраните токен — он больше не будет показан.
            </div>
            <code className="block break-all rounded-lg bg-slate-900 p-3 text-xs text-green-300">
              {created}
            </code>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(created);
                  toast.push("Скопировано", "info");
                }}
                className="btn-secondary"
              >
                Копировать
              </button>
              <button onClick={closeModal} className="btn-primary">
                Готово
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={create} className="space-y-4">
            <Field label="Название системы" required>
              <input
                className="input"
                placeholder="Система регистрации ТОО Алмас"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={closeModal} className="btn-secondary">
                Отмена
              </button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? "…" : "Создать"}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
