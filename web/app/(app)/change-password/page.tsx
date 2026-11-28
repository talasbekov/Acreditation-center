"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiException } from "@/lib/api";
import { homeFor, useAuth, type Me } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { Field, PageHeader } from "@/components/ui";

/** Смена пароля: старый + дважды новый (как `change_password` старой АЦ). */
export default function ChangePasswordPage() {
  const { me, setMe } = useAuth();
  const { t, err, msg } = useLang();
  const router = useRouter();
  const [form, setForm] = useState({ old_password: "", new_password: "", new_password_repeat: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [saving, setSaving] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    setErrors({});
    try {
      const updated = await api<Me>("/auth/change-password/", { method: "POST", body: form });
      setMe(updated);
      setDone(true);
      setForm({ old_password: "", new_password: "", new_password_repeat: "" });
    } catch (ex) {
      if (ex instanceof ApiException) {
        const text = err(ex.problem);
        if (ex.problem.field) setErrors({ [ex.problem.field]: ex.problem.type === "pw_weak" ? ex.problem.detail || text : text });
        else setError(text);
      } else setError(t("Не удалось подключиться к серверу"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <PageHeader title={me?.force_password_change ? t("Требуется смена пароля") : t("Изменить пароль")} />
      {me?.force_password_change && (
        <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t("Перед началом работы задайте новый пароль.")}
        </p>
      )}
      {done ? (
        <div className="card space-y-4 p-6">
          <p role="status" className="text-green-700">
            {msg("pw_changed")}
          </p>
          {me && (
            <button type="button" className="btn-primary" onClick={() => router.replace(homeFor(me))}>
              {t("На главную")}
            </button>
          )}
        </div>
      ) : (
        <form onSubmit={submit} className="card space-y-4 p-6">
          <Field label={t("Старый пароль")} required error={errors.old_password} htmlFor="old_password">
            <input id="old_password" type="password" autoComplete="current-password" className="input" value={form.old_password} onChange={set("old_password")} required />
          </Field>
          <Field label={t("Новый пароль")} required error={errors.new_password} htmlFor="new_password">
            <input id="new_password" type="password" autoComplete="new-password" className="input" value={form.new_password} onChange={set("new_password")} required />
          </Field>
          <Field label={t("Повторите пароль")} required error={errors.new_password_repeat} htmlFor="new_password_repeat">
            <input id="new_password_repeat" type="password" autoComplete="new-password" className="input" value={form.new_password_repeat} onChange={set("new_password_repeat")} required />
          </Field>
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
          <button type="submit" className="btn-primary" disabled={saving}>
            {t("Сохранить")}
          </button>
        </form>
      )}
    </div>
  );
}
