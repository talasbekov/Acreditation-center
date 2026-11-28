"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  API_BASE,
  ApiException,
  apiBlob,
  apiForm,
  downloadBlob,
} from "@/lib/api";
import { useToast } from "@/components/toast";
import { Badge, EmptyState, Modal, Spinner } from "@/components/ui";
import BadgePreview from "@/components/BadgePreview";
import type { BadgeLayout, BadgeTemplate, JobItem, Participant } from "@/lib/types";

/** Печать доступна только участникам с разрешённым доступом (Процесс 12). */
const PRINTABLE = "yes";

function fileUrl(path: string) {
  return API_BASE.replace(/\/api\/v1$/, "") + path;
}

function badgeName(p: Participant, source: "ru" | "en") {
  if (source === "en") {
    const en = `${p.last_name_en || ""} ${p.first_name_en || ""}`.trim();
    if (en) return en;
  }
  return `${p.last_name} ${p.first_name}`.trim();
}

export default function BadgesTab({ eventId }: { eventId: string }) {
  const toast = useToast();

  const [tpl, setTpl] = useState<BadgeTemplate | null>(null);
  const [layout, setLayout] = useState<BadgeLayout | null>(null);
  const [bgFile, setBgFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [parts, setParts] = useState<Participant[]>([]);
  const [loading, setLoading] = useState(true);
  const [onlyPending, setOnlyPending] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [printing, setPrinting] = useState(false);

  const [job, setJob] = useState<JobItem | null>(null);
  const [serverPreview, setServerPreview] = useState<string | null>(null);
  const previewUrlRef = useRef<string | null>(null);

  const loadTemplate = useCallback(async () => {
    const t = await api<BadgeTemplate>(`/events/${eventId}/badge-template`);
    setTpl(t);
    setLayout(t.layout);
  }, [eventId]);

  const loadParticipants = useCallback(async () => {
    const res = await api<{ data: Participant[] }>(`/events/${eventId}/participants`, {
      query: { access_status: PRINTABLE, per_page: 500 },
    });
    setParts(res.data || []);
  }, [eventId]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        await Promise.all([loadTemplate(), loadParticipants()]);
      } catch {
        toast.push("Не удалось загрузить данные бейджей", "error");
      } finally {
        setLoading(false);
      }
    })();
  }, [loadTemplate, loadParticipants, toast]);

  // Опрос фоновой задачи, как у ZIP-архива.
  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api<JobItem>(`/jobs/${job.id}`);
        setJob(fresh);
        if (fresh.status === "completed") {
          toast.push(`Бейджи готовы: ${fresh.result?.badge_count ?? 0} шт.`);
          loadParticipants();
        }
      } catch {
        /* следующая попытка через интервал */
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [job, toast, loadParticipants]);

  useEffect(
    () => () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    },
    []
  );

  const patch = (fn: (l: BadgeLayout) => BadgeLayout) =>
    setLayout((prev) => (prev ? fn(structuredClone(prev)) : prev));

  const saveTemplate = async () => {
    if (!layout) return;
    setSaving(true);
    setFieldErrors({});
    try {
      const form = new FormData();
      form.append("layout", JSON.stringify(layout));
      if (bgFile) form.append("background", bgFile);
      const saved = await apiForm<BadgeTemplate>(`/events/${eventId}/badge-template`, form);
      setTpl(saved);
      setLayout(saved.layout);
      setBgFile(null);
      toast.push("Шаблон сохранён");
    } catch (err) {
      if (err instanceof ApiException) {
        const map: Record<string, string> = {};
        err.body.details?.forEach((d) => (map[d.field] = d.message));
        setFieldErrors(map);
        toast.push(err.body.details?.length ? "Проверьте разметку" : err.message, "error");
      }
    } finally {
      setSaving(false);
    }
  };

  const resetTemplate = async () => {
    if (!confirm("Сбросить шаблон к настройкам по умолчанию?")) return;
    try {
      await api(`/events/${eventId}/badge-template`, { method: "DELETE" });
      setBgFile(null);
      await loadTemplate();
      toast.push("Шаблон сброшен");
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  const loadServerPreview = async (participantId?: string) => {
    try {
      const blob = await apiBlob(`/events/${eventId}/badges/preview`, {
        participant_id: participantId,
      });
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      const url = URL.createObjectURL(blob);
      previewUrlRef.current = url;
      setServerPreview(url);
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  const printOne = async (p: Participant) => {
    try {
      const blob = await apiBlob(`/events/${eventId}/participants/${p.id}/badge.pdf`);
      downloadBlob(blob, `badge-${p.last_name}-${p.id.slice(0, 8)}.pdf`);
      toast.push("Бейдж сформирован");
      loadParticipants();
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  const startJob = async (body: Record<string, unknown>, count: number) => {
    setPrinting(true);
    try {
      const res = await api<{ job_id: string; badge_count: number }>(
        `/events/${eventId}/badges`,
        { method: "POST", body }
      );
      setJob({
        id: res.job_id,
        type: "badge_pdf",
        status: "pending",
        created_at: new Date().toISOString(),
      });
      setSelected(new Set());
      toast.push(`Формируются бейджи: ${res.badge_count ?? count} шт.`);
    } catch (err) {
      if (err instanceof ApiException) {
        // 422: часть выбранных участников без разрешённого доступа.
        const blocked = err.body.participant_ids;
        if (blocked?.length) {
          const names = blocked
            .map((id) => {
              const p = parts.find((x) => x.id === id);
              return p ? `${p.last_name} ${p.first_name}` : id.slice(0, 8);
            })
            .join(", ");
          toast.push(`${err.message}: ${names}`, "error");
        } else {
          toast.push(err.message, "error");
        }
      }
    } finally {
      setPrinting(false);
    }
  };

  const downloadJob = async () => {
    const url = job?.result?.download_url;
    if (!url) return;
    try {
      const blob = await apiBlob(url.replace(/^\/api\/v1/, ""));
      downloadBlob(blob, `badges-${job?.id.slice(0, 8)}.pdf`);
    } catch (err) {
      if (err instanceof ApiException) toast.push(err.message, "error");
    }
  };

  if (loading || !layout || !tpl) return <Spinner />;

  const visible = onlyPending ? parts.filter((p) => !p.badge_printed_at) : parts;
  const allSelected = visible.length > 0 && visible.every((p) => selected.has(p.id));
  const pendingCount = parts.filter((p) => !p.badge_printed_at).length;

  const sampleName = visible[0]
    ? badgeName(visible[0], layout.name.source)
    : "Образец ФИО";

  return (
    <div className="space-y-8">
      {/* ---------- Шаблон ---------- */}
      <section>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold text-slate-900">Шаблон бейджа</h2>
          {tpl.is_default ? (
            <Badge color="gray">По умолчанию</Badge>
          ) : (
            <Badge color="blue">Свой шаблон</Badge>
          )}
        </div>
        <p className="mb-4 text-sm text-slate-500">
          Система рисует поверх фона только <b>фото</b> и <b>ФИО</b>. Разметка привязана
          к фону: заменили картинку — перемерьте координаты.
        </p>

        <div className="grid gap-6 lg:grid-cols-[1fr_420px]">
          <div className="card space-y-5 p-5">
            <Group title="Карточка">
              <Num
                label="Ширина, мм"
                value={layout.badge.width_mm}
                error={fieldErrors["layout.badge.width_mm"]}
                onChange={(v) => patch((l) => ((l.badge.width_mm = v), l))}
              />
              <Num
                label="Высота, мм"
                value={layout.badge.height_mm}
                error={fieldErrors["layout.badge.height_mm"]}
                onChange={(v) => patch((l) => ((l.badge.height_mm = v), l))}
              />
              <Num
                label="DPI печати"
                value={layout.badge.dpi}
                step={50}
                error={fieldErrors["layout.badge.dpi"]}
                onChange={(v) => patch((l) => ((l.badge.dpi = v), l))}
              />
            </Group>

            <Group
              title="Окно фото"
              toggle={{
                checked: layout.photo.enabled,
                onChange: (v) => patch((l) => ((l.photo.enabled = v), l)),
              }}
            >
              <Num
                label="X, мм"
                value={layout.photo.x_mm}
                error={fieldErrors["layout.photo.x_mm"]}
                onChange={(v) => patch((l) => ((l.photo.x_mm = v), l))}
              />
              <Num
                label="Y, мм"
                value={layout.photo.y_mm}
                error={fieldErrors["layout.photo.y_mm"]}
                onChange={(v) => patch((l) => ((l.photo.y_mm = v), l))}
              />
              <Num
                label="Ширина, мм"
                value={layout.photo.width_mm}
                error={fieldErrors["layout.photo.width_mm"]}
                onChange={(v) => patch((l) => ((l.photo.width_mm = v), l))}
              />
              <Num
                label="Высота, мм"
                value={layout.photo.height_mm}
                onChange={(v) => patch((l) => ((l.photo.height_mm = v), l))}
              />
              <Num
                label="Скругление, мм"
                value={layout.photo.corner_radius_mm}
                error={fieldErrors["layout.photo.corner_radius_mm"]}
                onChange={(v) => patch((l) => ((l.photo.corner_radius_mm = v), l))}
                hint="≥ половины стороны — круг"
              />
              <Num
                label="Якорь обрезки"
                value={layout.photo.focus_y}
                step={0.05}
                error={fieldErrors["layout.photo.focus_y"]}
                onChange={(v) => patch((l) => ((l.photo.focus_y = v), l))}
                hint="0 — верх, 1 — низ"
              />
            </Group>

            <Group title="ФИО">
              <div>
                <label className="label">Что печатать</label>
                <select
                  className="input"
                  value={layout.name.source}
                  onChange={(e) =>
                    patch((l) => ((l.name.source = e.target.value as "ru" | "en"), l))
                  }
                >
                  <option value="ru">Фамилия Имя (рус.)</option>
                  <option value="en">Транслитерация</option>
                </select>
              </div>
              <Num
                label="Высота строки"
                value={layout.name.y_fraction}
                step={0.01}
                error={fieldErrors["layout.name.y_fraction"]}
                onChange={(v) => patch((l) => ((l.name.y_fraction = v), l))}
                hint="доля высоты карточки"
              />
              <Num
                label="Левая граница"
                value={layout.name.x_start_fraction}
                step={0.01}
                error={fieldErrors["layout.name.x_start_fraction"]}
                onChange={(v) => patch((l) => ((l.name.x_start_fraction = v), l))}
              />
              <Num
                label="Правая граница"
                value={layout.name.x_end_fraction}
                step={0.01}
                onChange={(v) => patch((l) => ((l.name.x_end_fraction = v), l))}
              />
              <Num
                label="Кегль макс., pt"
                value={layout.name.max_font_pt}
                error={fieldErrors["layout.name.min_font_pt"]}
                onChange={(v) => patch((l) => ((l.name.max_font_pt = v), l))}
              />
              <Num
                label="Кегль мин., pt"
                value={layout.name.min_font_pt}
                onChange={(v) => patch((l) => ((l.name.min_font_pt = v), l))}
              />
              <Num
                label="Строк максимум"
                value={layout.name.max_lines}
                step={1}
                error={fieldErrors["layout.name.max_lines"]}
                onChange={(v) => patch((l) => ((l.name.max_lines = v), l))}
              />
              <div>
                <label className="label">Цвет текста</label>
                <div className="flex gap-2">
                  <input
                    type="color"
                    className="h-[38px] w-12 rounded-lg border border-slate-300"
                    value={layout.name.color}
                    onChange={(e) => patch((l) => ((l.name.color = e.target.value), l))}
                  />
                  <input
                    className="input font-mono"
                    value={layout.name.color}
                    onChange={(e) => patch((l) => ((l.name.color = e.target.value), l))}
                  />
                </div>
                {fieldErrors["layout.name.color"] && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors["layout.name.color"]}</p>
                )}
              </div>
              <label className="flex items-center gap-2 self-end pb-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={layout.name.wrap}
                  onChange={(e) => patch((l) => ((l.name.wrap = e.target.checked), l))}
                />
                Переносить длинные ФИО
              </label>
            </Group>

            <div>
              <label className="label">Фон бейджа (PNG/JPEG, до 5 МБ)</label>
              <input
                type="file"
                accept="image/png,image/jpeg"
                className="input"
                onChange={(e) => setBgFile(e.target.files?.[0] ?? null)}
              />
              <p className="mt-1 text-xs text-slate-500">
                {bgFile
                  ? `Выбран: ${bgFile.name} — будет загружен при сохранении`
                  : tpl.background_url
                    ? "Фон загружен. Новый файл заменит текущий."
                    : "Фон не загружен — используется стандартная заготовка."}
              </p>
            </div>

            <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
              <button onClick={saveTemplate} className="btn-primary" disabled={saving}>
                {saving ? "…" : "Сохранить шаблон"}
              </button>
              <button
                onClick={() => loadServerPreview(visible[0]?.id)}
                className="btn-secondary"
              >
                Предпросмотр с сервера
              </button>
              {!tpl.is_default && (
                <button onClick={resetTemplate} className="btn-ghost text-red-600">
                  Сбросить
                </button>
              )}
            </div>
          </div>

          <div className="card space-y-3 p-5">
            <div className="text-xs uppercase text-slate-400">Предпросмотр</div>
            <BadgePreview
              layout={layout}
              name={sampleName}
              backgroundUrl={tpl.background_url ? fileUrl(tpl.background_url) : undefined}
              className="rounded-lg border border-slate-200"
            />
            <p className="text-xs text-slate-500">
              Рисуется по несохранённым настройкам. Пунктир — границы окон, на печать
              они не идут. Размер карточки: {layout.badge.width_mm} × {layout.badge.height_mm} мм
              при {layout.badge.dpi} DPI.
            </p>
          </div>
        </div>
      </section>

      {/* ---------- Печать ---------- */}
      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-900">Печать бейджей</h2>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => startJob({ participant_ids: Array.from(selected) }, selected.size)}
              className="btn-primary"
              disabled={selected.size === 0 || printing}
            >
              🖨 Печать выбранных ({selected.size})
            </button>
            <button
              onClick={() => startJob({ print_all_pending: true }, pendingCount)}
              className="btn-secondary"
              disabled={pendingCount === 0 || printing}
            >
              Печать всем, кому положено ({pendingCount})
            </button>
          </div>
        </div>

        <p className="mb-3 text-sm text-slate-500">
          Бейдж печатается только участникам с <b>разрешённым доступом</b>. Перепечатка
          доступна всегда — отметка о печати её не блокирует.
        </p>

        {job && (
          <div className="card mb-4 p-4">
            {job.status === "completed" ? (
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-3">
                  <Badge color="green">Готово</Badge>
                  <span className="text-sm text-slate-600">
                    Бейджей в файле: <b>{job.result?.badge_count ?? 0}</b>
                  </span>
                  <button onClick={downloadJob} className="btn-primary text-xs">
                    ⬇ Скачать PDF
                  </button>
                  <button onClick={() => setJob(null)} className="btn-ghost text-xs">
                    Скрыть
                  </button>
                </div>
                {!!job.result?.warnings?.length && (
                  <ul className="space-y-1 rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
                    {job.result.warnings.map((wn, i) => {
                      const p = parts.find((x) => x.id === wn.participant_id);
                      return (
                        <li key={i}>
                          <b>{p ? `${p.last_name} ${p.first_name}` : wn.participant_id.slice(0, 8)}</b>
                          : {wn.message}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            ) : job.status === "failed" ? (
              <div className="flex items-center gap-3">
                <Badge color="red">Ошибка</Badge>
                <button onClick={() => setJob(null)} className="btn-ghost text-xs">
                  Скрыть
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3 text-sm text-slate-600">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600" />
                Формируется PDF…
              </div>
            )}
          </div>
        )}

        <label className="mb-3 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={onlyPending}
            onChange={(e) => setOnlyPending(e.target.checked)}
          />
          Только те, кому ещё не печатали
        </label>

        {visible.length === 0 ? (
          <EmptyState
            text={
              parts.length === 0
                ? "Нет участников с разрешённым доступом — сначала исполните результат проверки"
                : "Всем участникам бейджи уже напечатаны"
            }
          />
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={() =>
                        setSelected(allSelected ? new Set() : new Set(visible.map((p) => p.id)))
                      }
                    />
                  </th>
                  <th className="px-4 py-3">Участник</th>
                  <th className="px-4 py-3">На бейдже</th>
                  <th className="px-4 py-3">Бейдж</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visible.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selected.has(p.id)}
                        onChange={() =>
                          setSelected((prev) => {
                            const next = new Set(prev);
                            if (next.has(p.id)) next.delete(p.id);
                            else next.add(p.id);
                            return next;
                          })
                        }
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">
                        {p.last_name} {p.first_name} {p.middle_name}
                      </div>
                      <div className="text-xs text-slate-400">{p.position || "—"}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {badgeName(p, layout.name.source)}
                    </td>
                    <td className="px-4 py-3">
                      {p.badge_printed_at ? (
                        <div className="flex flex-col gap-1">
                          <Badge color="green">Напечатан</Badge>
                          <span className="text-xs text-slate-400">
                            {new Date(p.badge_printed_at).toLocaleString("ru-RU")}
                          </span>
                        </div>
                      ) : (
                        <Badge color="gray">Не печатался</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => printOne(p)} className="btn-secondary text-xs">
                        🖨 {p.badge_printed_at ? "Перепечатать" : "Бейдж"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Modal
        open={!!serverPreview}
        onClose={() => setServerPreview(null)}
        title="Предпросмотр с сервера"
      >
        {serverPreview && (
          <div className="space-y-3">
            <img src={serverPreview} alt="Бейдж" className="w-full rounded-lg border border-slate-200" />
            <p className="text-xs text-slate-500">
              Так карточку рисует бэкенд по <b>сохранённому</b> шаблону. Если картинка
              отличается от предпросмотра слева — сохраните разметку.
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}

function Group({
  title,
  toggle,
  children,
}: {
  title: string;
  toggle?: { checked: boolean; onChange: (v: boolean) => void };
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h3>
        {toggle && (
          <label className="flex items-center gap-1.5 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={toggle.checked}
              onChange={(e) => toggle.onChange(e.target.checked)}
            />
            включено
          </label>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">{children}</div>
    </div>
  );
}

function Num({
  label,
  value,
  onChange,
  step = 0.1,
  hint,
  error,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  hint?: string;
  error?: string;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <input
        type="number"
        step={step}
        className="input"
        value={Number.isFinite(value) ? value : 0}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
      />
      {error ? (
        <p className="mt-1 text-xs text-red-600">{error}</p>
      ) : (
        hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>
      )}
    </div>
  );
}
