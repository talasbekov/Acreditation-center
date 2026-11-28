"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiException } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { useToast } from "@/components/toast";
import { Badge, EmptyState, Field, Modal, Spinner } from "@/components/ui";
import type { EventItem } from "@/lib/types";

const empty = {
  code: "",
  name_ru: "",
  name_kz: "",
  name_en: "",
  city: "",
  start_date: "",
  end_date: "",
};

export default function EventsPage() {
  const { isAdmin } = useAuth();
  const { t, eventName } = useLang();
  const toast = useToast();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<EventItem | null>(null);
  const [form, setForm] = useState(empty);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<{ data: EventItem[] }>("/events", {
        query: { search, per_page: 100 },
      });
      setEvents(res.data || []);
    } catch {
      toast.push("Не удалось загрузить мероприятия", "error");
    } finally {
      setLoading(false);
    }
  }, [search, toast]);

  useEffect(() => {
    const id = setTimeout(load, 250);
    return () => clearTimeout(id);
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(empty);
    setErrors({});
    setModalOpen(true);
  };

  const openEdit = (e: EventItem) => {
    setEditing(e);
    setForm({
      code: e.code,
      name_ru: e.name_ru,
      name_kz: e.name_kz,
      name_en: e.name_en,
      city: e.city,
      start_date: e.start_date,
      end_date: e.end_date,
    });
    setErrors({});
    setModalOpen(true);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrors({});
    try {
      if (editing) {
        await api(`/events/${editing.id}`, { method: "PUT", body: form });
        toast.push("Мероприятие обновлено");
      } else {
        await api("/events", { method: "POST", body: form });
        toast.push("Мероприятие создано");
      }
      setModalOpen(false);
      load();
    } catch (err) {
      if (err instanceof ApiException) {
        if (err.body.details) {
          const map: Record<string, string> = {};
          err.body.details.forEach((d) => (map[d.field] = d.message));
          setErrors(map);
        } else {
          toast.push(err.message, "error");
        }
      }
    } finally {
      setSaving(false);
    }
  };

  const remove = async (e: EventItem) => {
    if (!confirm(`Удалить мероприятие «${e.name_ru}» вместе со всеми участниками и файлами?`))
      return;
    try {
      await api(`/events/${e.id}`, { method: "DELETE" });
      toast.push("Мероприятие удалено");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  const toggleArchive = async (e: EventItem) => {
    try {
      await api(`/events/${e.id}/archive-toggle`, {
        method: "POST",
        body: { is_archived: !e.is_archived },
      });
      toast.push(e.is_archived ? "Убрано из архива" : "Добавлено в архив");
      load();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900">{t("events")}</h1>
        {isAdmin && (
          <button onClick={openCreate} className="btn-primary">
            + {t("create")}
          </button>
        )}
      </div>

      <div className="mb-4">
        <input
          className="input max-w-md"
          placeholder={`${t("search")}…`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <Spinner />
      ) : events.length === 0 ? (
        <EmptyState text="Мероприятий пока нет" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {events.map((e) => (
            <div key={e.id} className="card flex flex-col p-5">
              <div className="mb-2 flex items-start justify-between gap-2">
                <span className="badge bg-slate-100 font-mono text-slate-600">
                  {e.code}
                </span>
                {e.is_archived && <Badge color="amber">Архив</Badge>}
              </div>
              <Link
                href={`/events/${e.id}`}
                className="mb-1 text-lg font-semibold text-slate-900 hover:text-brand-700"
              >
                {eventName(e)}
              </Link>
              <div className="mb-4 space-y-1 text-sm text-slate-500">
                <div>📍 {e.city || "—"}</div>
                <div>
                  🗓 {e.start_date} — {e.end_date}
                </div>
                <div>👤 {e.participant_count} участников</div>
              </div>
              <div className="mt-auto flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                <Link href={`/events/${e.id}`} className="btn-secondary text-xs">
                  Открыть
                </Link>
                {isAdmin ? (
                  <>
                    <button onClick={() => openEdit(e)} className="btn-ghost text-xs">
                      {t("edit")}
                    </button>
                    <button onClick={() => remove(e)} className="btn-ghost text-xs text-red-600">
                      {t("delete")}
                    </button>
                  </>
                ) : (
                  <button onClick={() => toggleArchive(e)} className="btn-ghost text-xs">
                    {e.is_archived ? "Из архива" : "В архив"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? "Редактировать мероприятие" : "Новое мероприятие"}
        wide
      >
        <form onSubmit={save} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("code")} required error={errors.code}>
              <input
                className="input"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
              />
            </Field>
            <Field label={t("city")}>
              <input
                className="input"
                value={form.city}
                onChange={(e) => setForm({ ...form, city: e.target.value })}
              />
            </Field>
          </div>
          <Field label="Название (рус)" required error={errors.name}>
            <input
              className="input"
              value={form.name_ru}
              onChange={(e) => setForm({ ...form, name_ru: e.target.value })}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Атауы (қаз)" required>
              <input
                className="input"
                value={form.name_kz}
                onChange={(e) => setForm({ ...form, name_kz: e.target.value })}
              />
            </Field>
            <Field label="Name (eng)" required>
              <input
                className="input"
                value={form.name_en}
                onChange={(e) => setForm({ ...form, name_en: e.target.value })}
              />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Дата начала" required error={errors.dates}>
              <input
                type="date"
                className="input"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              />
            </Field>
            <Field label="Дата окончания" required error={errors.end_date}>
              <input
                type="date"
                className="input"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
            </Field>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setModalOpen(false)} className="btn-secondary">
              {t("cancel")}
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "…" : t("save")}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
