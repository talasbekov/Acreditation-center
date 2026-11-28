"use client";

import { useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { EventBrief } from "@/lib/types";
import { Field } from "../ui";

/**
 * «Добавить участника аккредитации» (оператора) — форма `add_operator` с главной
 * администратора и карточки мероприятия: ФИО, логин, email, место работы, телефон,
 * мероприятие. Пароль не задаётся: оператору уходит письмо со ссылкой.
 */
export default function OperatorCreateForm({
  events,
  defaultEventId,
  onDone,
}: {
  events: EventBrief[];
  defaultEventId?: number;
  onDone: (message: string, ok: boolean) => void;
}) {
  const { t } = useLang();
  const empty = {
    last_name: "",
    first_name: "",
    patronymic: "",
    login: "",
    email: "",
    workplace: "",
    phone_number: "",
    event: String(defaultEventId ?? events[0]?.id ?? ""),
  };
  const [v, setV] = useState(empty);
  const [saving, setSaving] = useState(false);
  const set = (k: keyof typeof empty) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setV((s) => ({ ...s, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const r = await api<{ message: string; email_sent: boolean }>("/admin/operators/", { method: "POST", body: v });
      setV(empty);
      onDone(r.message, r.email_sent);
    } catch (ex) {
      onDone(ex instanceof ApiException ? String(ex.problem.detail || ex.message) : t("Не удалось подключиться к серверу"), false);
    } finally {
      setSaving(false);
    }
  };

  const text = (k: keyof typeof empty, label: string, type = "text") => (
    <Field label={t(label)} required htmlFor={`op-${k}`}>
      <input id={`op-${k}`} type={type} className="input" required value={v[k]} onChange={set(k)} />
    </Field>
  );

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        {text("last_name", "Фамилия")}
        {text("first_name", "Имя")}
        {text("patronymic", "Отчество")}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {text("login", "Логин")}
        {text("email", "Email оператора", "email")}
        {text("workplace", "Место работы")}
        {text("phone_number", "Контактные данные")}
      </div>
      <Field label={t("Мероприятие")} required htmlFor="op-event">
        <select id="op-event" className="input" required value={v.event} onChange={set("event")}>
          {events.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name_rus}
            </option>
          ))}
        </select>
      </Field>
      <button type="submit" className="btn-primary w-full" disabled={saving || !events.length}>
        {t("Добавить участника аккредитации")}
      </button>
    </form>
  );
}
