"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Badge, EmptyState, Field, Modal, Spinner } from "@/components/ui";
import type { CustomField } from "@/lib/types";

const blank = {
  field_name: "",
  field_type: "text" as CustomField["field_type"],
  is_required: false,
  options: "",
};

export default function FieldsTab({ eventId }: { eventId: string }) {
  const toast = useToast();
  const [fields, setFields] = useState<CustomField[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<{ data: CustomField[] }>(`/events/${eventId}/custom-fields`);
      setFields(res.data || []);
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
      await api(`/events/${eventId}/custom-fields`, {
        method: "POST",
        body: {
          field_name: form.field_name,
          field_type: form.field_type,
          is_required: form.is_required,
          options:
            form.field_type === "select"
              ? form.options.split(",").map((s) => s.trim()).filter(Boolean)
              : null,
          sort_order: fields.length + 1,
        },
      });
      toast.push("Поле создано");
      setOpen(false);
      setForm(blank);
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (f: CustomField) => {
    if (!confirm(`Удалить поле «${f.field_name}»?`)) return;
    try {
      await api(`/custom-fields/${f.id}`, { method: "DELETE" });
      toast.push("Поле удалено");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  if (loading) return <Spinner />;

  const typeLabel: Record<string, string> = {
    text: "Текст",
    number: "Число",
    date: "Дата",
    select: "Список",
  };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Поля отображаются при добавлении участника и в форме саморегистрации.
        </p>
        <button onClick={() => setOpen(true)} className="btn-primary">
          + Добавить поле
        </button>
      </div>

      {fields.length === 0 ? (
        <EmptyState text="Дополнительных полей пока нет" />
      ) : (
        <div className="card divide-y divide-slate-100">
          {fields.map((f) => (
            <div key={f.id} className="flex items-center justify-between px-5 py-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-900">{f.field_name}</span>
                  {f.is_required && <Badge color="red">Обязательное</Badge>}
                </div>
                <div className="text-xs text-slate-400">
                  {typeLabel[f.field_type]}
                  {f.options && f.options.length > 0 && ` · ${f.options.join(", ")}`}
                </div>
              </div>
              <button onClick={() => remove(f)} className="btn-ghost text-xs text-red-600">
                Удалить
              </button>
            </div>
          ))}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Новое поле">
        <form onSubmit={create} className="space-y-4">
          <Field label="Название поля" required>
            <input
              className="input"
              value={form.field_name}
              onChange={(e) => setForm({ ...form, field_name: e.target.value })}
            />
          </Field>
          <Field label="Тип">
            <select
              className="input"
              value={form.field_type}
              onChange={(e) =>
                setForm({ ...form, field_type: e.target.value as CustomField["field_type"] })
              }
            >
              <option value="text">Текст</option>
              <option value="number">Число</option>
              <option value="date">Дата</option>
              <option value="select">Список</option>
            </select>
          </Field>
          {form.field_type === "select" && (
            <Field label="Варианты (через запятую)">
              <input
                className="input"
                placeholder="временный, постоянный"
                value={form.options}
                onChange={(e) => setForm({ ...form, options: e.target.value })}
              />
            </Field>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_required}
              onChange={(e) => setForm({ ...form, is_required: e.target.checked })}
            />
            Обязательное поле
          </label>
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
