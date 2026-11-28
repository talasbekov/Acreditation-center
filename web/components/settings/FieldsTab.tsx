"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { CustomField } from "@/lib/types";
import Notice, { type NoticeValue } from "../Notice";
import { ConfirmButton, EmptyState, Field } from "../ui";

const TYPES: { value: CustomField["field_type"]; label: string }[] = [
  { value: "text", label: "Текст" },
  { value: "number", label: "Число" },
  { value: "date", label: "Дата" },
  { value: "select", label: "Список" },
];

/** Дополнительные поля мероприятия: показываются в форме участника и саморегистрации. */
export default function FieldsTab({ eventId }: { eventId: string }) {
  const { t, err } = useLang();
  const [fields, setFields] = useState<CustomField[]>([]);
  const [notice, setNotice] = useState<NoticeValue>(null);
  const empty = { field_name: "", field_type: "text" as CustomField["field_type"], is_required: false, options: "" };
  const [form, setForm] = useState(empty);

  const load = useCallback(async () => {
    const r = await api<{ results: CustomField[] }>(`/events/${eventId}/custom-fields/`);
    setFields(r.results);
  }, [eventId]);
  useEffect(() => {
    load();
  }, [load]);

  const fail = (e: unknown) => setNotice({ ok: false, text: e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу") });

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api(`/events/${eventId}/custom-fields/`, { method: "POST", body: form });
      setForm(empty);
      setNotice({ ok: true, text: t("Поле добавлено") });
      await load();
    } catch (ex) {
      fail(ex);
    }
  };

  const toggleRequired = async (f: CustomField) => {
    try {
      await api(`/custom-fields/${f.id}/`, { method: "PATCH", body: { is_required: !f.is_required } });
      await load();
    } catch (ex) {
      fail(ex);
    }
  };

  const remove = async (f: CustomField) => {
    try {
      await api(`/custom-fields/${f.id}/`, { method: "DELETE" });
      await load();
    } catch (ex) {
      fail(ex);
    }
  };

  return (
    <div className="space-y-6">
      <Notice value={notice} />
      {fields.length === 0 ? (
        <EmptyState text={t("Дополнительных полей нет")} />
      ) : (
        <ul className="card divide-y divide-slate-100">
          {fields.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <div>
                <span className="font-medium">{f.field_name}</span>
                <span className="ml-2 text-xs text-slate-500">
                  {t(TYPES.find((x) => x.value === f.field_type)?.label || f.field_type)}
                  {f.field_type === "select" && `: ${f.options.join(", ")}`}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1 text-sm">
                  <input type="checkbox" checked={f.is_required} onChange={() => toggleRequired(f)} />
                  {t("Обязательное")}
                </label>
                <ConfirmButton className="btn-ghost px-2 py-1 text-xs text-red-700" question={t("Удалить поле «{name}»?", { name: f.field_name })} onConfirm={() => remove(f)}>
                  {t("Удалить")}
                </ConfirmButton>
              </div>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={add} className="card space-y-4 p-5">
        <h3 className="font-semibold">{t("Новое поле")}</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("Название поля")} required htmlFor="cf-name">
            <input id="cf-name" className="input" required maxLength={255} value={form.field_name} onChange={(e) => setForm({ ...form, field_name: e.target.value })} />
          </Field>
          <Field label={t("Тип")} htmlFor="cf-type">
            <select id="cf-type" className="input" value={form.field_type} onChange={(e) => setForm({ ...form, field_type: e.target.value as CustomField["field_type"] })}>
              {TYPES.map((x) => (
                <option key={x.value} value={x.value}>
                  {t(x.label)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {form.field_type === "select" && (
          <Field label={t("Варианты, по одному в строке")} required htmlFor="cf-options">
            <textarea id="cf-options" className="input" rows={4} required value={form.options} onChange={(e) => setForm({ ...form, options: e.target.value })} />
          </Field>
        )}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.is_required} onChange={(e) => setForm({ ...form, is_required: e.target.checked })} />
          {t("Обязательное")}
        </label>
        <button type="submit" className="btn-primary">
          {t("Добавить поле")}
        </button>
      </form>
    </div>
  );
}
