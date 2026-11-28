"use client";

import { useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { Field } from "@/components/ui";
import type { CustomField, Participant } from "@/lib/types";

export interface ParticipantPayload {
  last_name: string;
  first_name: string;
  middle_name: string;
  last_name_en: string;
  first_name_en: string;
  iin: string;
  birth_date: string;
  gender: "male" | "female";
  citizenship: string;
  position: string;
  doc_type: string;
  doc_series: string;
  doc_number: string;
  doc_issued_date: string;
  doc_expiry_date: string;
  visit_objects: string;
  category: string;
  custom_field_values: Record<string, string>;
}

const blank: ParticipantPayload = {
  last_name: "",
  first_name: "",
  middle_name: "",
  last_name_en: "",
  first_name_en: "",
  iin: "",
  birth_date: "",
  gender: "male",
  citizenship: "Казахстан",
  position: "",
  doc_type: "passport",
  doc_series: "",
  doc_number: "",
  doc_issued_date: "",
  doc_expiry_date: "",
  visit_objects: "",
  category: "",
  custom_field_values: {},
};

export function participantToPayload(p: Participant): ParticipantPayload {
  return {
    last_name: p.last_name,
    first_name: p.first_name,
    middle_name: p.middle_name || "",
    last_name_en: p.last_name_en || "",
    first_name_en: p.first_name_en || "",
    iin: p.iin || "",
    birth_date: p.birth_date,
    gender: p.gender,
    citizenship: p.citizenship,
    position: p.position || "",
    doc_type: p.doc_type,
    doc_series: p.doc_series || "",
    doc_number: p.doc_number,
    doc_issued_date: p.doc_issued_date,
    doc_expiry_date: p.doc_expiry_date,
    visit_objects: p.visit_objects || "",
    category: p.category || "",
    custom_field_values: p.custom_field_values || {},
  };
}

interface Props {
  eventId?: string;
  fields?: CustomField[];
  initial?: ParticipantPayload;
  submitLabel: string;
  onSubmit: (payload: ParticipantPayload) => Promise<void>;
  onCancel: () => void;
}

export default function ParticipantForm({
  eventId,
  fields: fieldsProp,
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: Props) {
  const [form, setForm] = useState<ParticipantPayload>(initial || blank);
  const [fields, setFields] = useState<CustomField[]>(fieldsProp || []);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (fieldsProp || !eventId) return;
    api<{ data: CustomField[] }>(`/events/${eventId}/custom-fields`)
      .then((r) => setFields(r.data || []))
      .catch(() => {});
  }, [eventId, fieldsProp]);

  const set = (k: keyof ParticipantPayload, v: string) =>
    setForm((f) => ({ ...f, [k]: v }));
  const setCustom = (id: string, v: string) =>
    setForm((f) => ({
      ...f,
      custom_field_values: { ...f.custom_field_values, [id]: v },
    }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrors({});
    try {
      await onSubmit(form);
    } catch (err) {
      if (err instanceof ApiException) {
        if (err.body.details) {
          const map: Record<string, string> = {};
          err.body.details.forEach((d) => (map[d.field] = d.message));
          setErrors(map);
        } else {
          setErrors({ _: err.message });
        }
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Фамилия" required error={errors.last_name}>
          <input className="input" value={form.last_name} onChange={(e) => set("last_name", e.target.value)} />
        </Field>
        <Field label="Имя" required error={errors.first_name}>
          <input className="input" value={form.first_name} onChange={(e) => set("first_name", e.target.value)} />
        </Field>
        <Field label="Отчество">
          <input className="input" value={form.middle_name} onChange={(e) => set("middle_name", e.target.value)} />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Фамилия (транслит)" error={errors.last_name_en}>
          <input className="input" value={form.last_name_en} onChange={(e) => set("last_name_en", e.target.value)} />
        </Field>
        <Field label="Имя (транслит)" error={errors.first_name_en}>
          <input className="input" value={form.first_name_en} onChange={(e) => set("first_name_en", e.target.value)} />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="Дата рождения" required error={errors.birth_date}>
          <input type="date" className="input" value={form.birth_date} onChange={(e) => set("birth_date", e.target.value)} />
        </Field>
        <Field label="Пол" required error={errors.gender}>
          <select className="input" value={form.gender} onChange={(e) => set("gender", e.target.value)}>
            <option value="male">Мужской</option>
            <option value="female">Женский</option>
          </select>
        </Field>
        <Field label="Гражданство" required error={errors.citizenship}>
          <input className="input" value={form.citizenship} onChange={(e) => set("citizenship", e.target.value)} />
        </Field>
        <Field label="ИИН" error={errors.iin}>
          <input className="input" value={form.iin} onChange={(e) => set("iin", e.target.value)} placeholder="12 цифр" />
        </Field>
      </div>

      <Field label="Должность">
        <input className="input" value={form.position} onChange={(e) => set("position", e.target.value)} />
      </Field>

      <div className="rounded-lg bg-slate-50 p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Документ</p>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Тип" required error={errors.doc_type}>
            <select className="input" value={form.doc_type} onChange={(e) => set("doc_type", e.target.value)}>
              <option value="passport">Паспорт</option>
              <option value="id_card">Удостоверение</option>
              <option value="other">Другое</option>
            </select>
          </Field>
          <Field label="Серия">
            <input className="input" value={form.doc_series} onChange={(e) => set("doc_series", e.target.value)} />
          </Field>
          <Field label="Номер" required error={errors.doc_number}>
            <input className="input" value={form.doc_number} onChange={(e) => set("doc_number", e.target.value)} />
          </Field>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field label="Дата выдачи" required error={errors.doc_issued_date}>
            <input type="date" className="input" value={form.doc_issued_date} onChange={(e) => set("doc_issued_date", e.target.value)} />
          </Field>
          <Field label="Действителен до" required error={errors.doc_expiry_date}>
            <input type="date" className="input" value={form.doc_expiry_date} onChange={(e) => set("doc_expiry_date", e.target.value)} />
          </Field>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Объекты посещения">
          <input className="input" value={form.visit_objects} onChange={(e) => set("visit_objects", e.target.value)} />
        </Field>
        <Field label="Категория">
          <input className="input" value={form.category} onChange={(e) => set("category", e.target.value)} />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Фотография (JPEG/PNG)" required>
          <input type="file" accept="image/jpeg,image/png" className="input py-1.5 text-xs" />
        </Field>
        <Field label="Скан документа (JPEG/PNG/PDF)" required>
          <input type="file" accept="image/jpeg,image/png,application/pdf" className="input py-1.5 text-xs" />
        </Field>
      </div>

      {fields.length > 0 && (
        <div className="rounded-lg bg-brand-50 p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-brand-700">
            Дополнительные поля
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {fields.map((f) => (
              <Field key={f.id} label={f.field_name} required={f.is_required} error={errors[f.id]}>
                {f.field_type === "select" ? (
                  <select
                    className="input"
                    value={form.custom_field_values[f.id] || ""}
                    onChange={(e) => setCustom(f.id, e.target.value)}
                  >
                    <option value="">—</option>
                    {(f.options || []).map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={f.field_type === "number" ? "number" : f.field_type === "date" ? "date" : "text"}
                    className="input"
                    value={form.custom_field_values[f.id] || ""}
                    onChange={(e) => setCustom(f.id, e.target.value)}
                  />
                )}
              </Field>
            ))}
          </div>
        </div>
      )}

      {errors._ && <div className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{errors._}</div>}

      <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
        <button type="button" onClick={onCancel} className="btn-secondary">
          Отмена
        </button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
