"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Badge, EmptyState, Field, Modal, Spinner } from "@/components/ui";
import type { Operator } from "@/lib/types";

const blank = {
  full_name: "",
  login: "",
  phone: "",
  organization: "",
  role: "operator",
};

export default function OperatorsPage() {
  const toast = useToast();
  const [operators, setOperators] = useState<Operator[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [saving, setSaving] = useState(false);
  const [password, setPassword] = useState<{ login: string; pw: string } | null>(null);

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

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await api<{ generated_password: string; login: string }>("/operators", {
        method: "POST",
        body: form,
      });
      setPassword({ login: res.login, pw: res.generated_password });
      setForm(blank);
      setOpen(false);
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const reset = async (o: Operator) => {
    if (!confirm(`Сбросить пароль оператору ${o.full_name}?`)) return;
    try {
      const res = await api<{ generated_password: string }>(
        `/operators/${o.id}/reset-password`,
        { method: "POST" }
      );
      setPassword({ login: o.login, pw: res.generated_password });
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  const remove = async (o: Operator) => {
    if (!confirm(`Удалить оператора ${o.full_name}?`)) return;
    try {
      await api(`/operators/${o.id}`, { method: "DELETE" });
      toast.push("Оператор удалён");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Операторы</h1>
        <button onClick={() => setOpen(true)} className="btn-primary">
          + Создать оператора
        </button>
      </div>

      {loading ? (
        <Spinner />
      ) : operators.length === 0 ? (
        <EmptyState text="Операторов пока нет" />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Оператор</th>
                <th className="px-4 py-3">Организация</th>
                <th className="px-4 py-3">Роль</th>
                <th className="px-4 py-3">Мероприятий</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {operators.map((o) => (
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
                  <td className="px-4 py-3 text-slate-600">{o.events?.length || 0}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <button onClick={() => reset(o)} className="btn-ghost text-xs">
                        Сбросить пароль
                      </button>
                      <button onClick={() => remove(o)} className="btn-ghost text-xs text-red-600">
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Новый оператор">
        <form onSubmit={create} className="space-y-4">
          <Field label="ФИО" required>
            <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Логин" required>
              <input className="input" value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} />
            </Field>
            <Field label="Телефон">
              <input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
          </div>
          <Field label="Организация">
            <input className="input" value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} />
          </Field>
          <Field label="Роль">
            <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="operator">Оператор</option>
              <option value="superoperator">Супероператор</option>
            </select>
          </Field>
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

      <Modal open={!!password} onClose={() => setPassword(null)} title="Пароль сгенерирован">
        {password && (
          <div className="space-y-4">
            <div className="rounded-lg bg-amber-50 p-4 text-sm text-amber-800">
              Пароль показывается один раз. Передайте его оператору.
            </div>
            <div className="rounded-lg bg-slate-900 p-4 text-center">
              <div className="text-xs text-slate-400">Логин: {password.login}</div>
              <code className="text-lg font-bold text-green-300">{password.pw}</code>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(password.pw);
                  toast.push("Скопировано", "info");
                }}
                className="btn-secondary"
              >
                Копировать
              </button>
              <button onClick={() => setPassword(null)} className="btn-primary">
                Готово
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
