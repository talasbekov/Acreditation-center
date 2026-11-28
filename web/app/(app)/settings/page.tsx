"use client";

import { useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/toast";
import { Field } from "@/components/ui";

export default function SettingsPage() {
  const { session, isAdmin } = useAuth();
  const toast = useToast();
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (newPw !== confirm) {
      setError("Новые пароли не совпадают");
      return;
    }
    setSaving(true);
    try {
      await api("/auth/change-password", {
        method: "POST",
        body: {
          old_password: oldPw,
          new_password: newPw,
          new_password_confirm: confirm,
        },
      });
      toast.push("Пароль изменён");
      setOldPw("");
      setNewPw("");
      setConfirm("");
    } catch (err) {
      if (err instanceof ApiException) setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Настройки</h1>

      <div className="card mb-6 p-6">
        <h2 className="mb-1 font-semibold text-slate-900">Профиль</h2>
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-slate-400">ФИО</dt>
          <dd className="text-slate-800">{session?.user.full_name}</dd>
          <dt className="text-slate-400">Логин</dt>
          <dd className="text-slate-800">{session?.user.login}</dd>
          <dt className="text-slate-400">Роль</dt>
          <dd className="text-slate-800">{isAdmin ? "Администратор" : "Оператор"}</dd>
        </dl>
      </div>

      <div className="card p-6">
        <h2 className="mb-4 font-semibold text-slate-900">Сменить пароль</h2>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Старый пароль" required>
            <input type="password" className="input" value={oldPw} onChange={(e) => setOldPw(e.target.value)} />
          </Field>
          <Field label="Новый пароль" required>
            <input type="password" className="input" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
          </Field>
          <Field label="Повторите новый пароль" required>
            <input type="password" className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </Field>
          {error && <div className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "…" : "Сменить пароль"}
          </button>
        </form>
      </div>
    </div>
  );
}
