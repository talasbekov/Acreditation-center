"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiException, apiBlobPost, download } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { BadgeCandidate, BadgeLayout, BadgeTemplateInfo, JobInfo } from "@/lib/types";
import Notice, { type NoticeValue } from "@/components/Notice";
import StaffShell from "@/components/staff/StaffShell";
import { Badge, ConfirmButton, PageHeader, Spinner, formatDateTime } from "@/components/ui";

type NumKey = [keyof BadgeLayout, string, string, number?];

const NUMBERS: NumKey[] = [
  ["badge", "width_mm", "Ширина карточки, мм"],
  ["badge", "height_mm", "Высота карточки, мм"],
  ["badge", "dpi", "Разрешение, DPI", 1],
  ["photo", "x_mm", "Фото: отступ слева, мм"],
  ["photo", "y_mm", "Фото: отступ сверху, мм"],
  ["photo", "width_mm", "Фото: ширина, мм"],
  ["photo", "height_mm", "Фото: высота, мм"],
  ["photo", "radius_mm", "Фото: скругление, мм"],
  ["name", "x0", "ФИО: левая граница (доля)", 0.01],
  ["name", "x1", "ФИО: правая граница (доля)", 0.01],
  ["name", "y", "ФИО: верх (доля)", 0.01],
  ["name", "line_height", "ФИО: высота строки (доля)", 0.01],
  ["name", "max_pt", "ФИО: максимальный кегль, пт", 0.5],
  ["name", "min_pt", "ФИО: минимальный кегль, пт", 0.5],
];

/** Бейджи мероприятия (процесс 12): шаблон, предпросмотр, печать одного и пакетом. */
function BadgesPage({ eventId }: { eventId: string }) {
  const { t, err } = useLang();
  const [tpl, setTpl] = useState<BadgeTemplateInfo | null>(null);
  const [layout, setLayout] = useState<BadgeLayout | null>(null);
  const [nameSource, setNameSource] = useState<"ru" | "latin">("ru");
  const [bg, setBg] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [rows, setRows] = useState<BadgeCandidate[] | null>(null);
  const [access, setAccess] = useState("yes");
  const [printed, setPrinted] = useState("false");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [job, setJob] = useState<JobInfo | null>(null);
  const [notice, setNotice] = useState<NoticeValue>(null);
  const previewFor = useRef<number | undefined>(undefined);

  const fail = useCallback(
    (e: unknown) => setNotice({ ok: false, text: e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу") }),
    [err, t],
  );

  const loadTemplate = useCallback(async () => {
    const data = await api<BadgeTemplateInfo>(`/events/${eventId}/badge-template/`);
    setTpl(data);
    setLayout(data.layout);
    setNameSource(data.name_source);
  }, [eventId]);

  const loadRows = useCallback(async () => {
    const r = await api<{ results: BadgeCandidate[] }>(`/events/${eventId}/badges/candidates/`, {
      query: { access: access || undefined, printed: printed || undefined, search: search || undefined },
    });
    setRows(r.results);
    setSelected(new Set());
  }, [eventId, access, printed, search]);

  useEffect(() => {
    loadTemplate().catch(fail);
  }, [loadTemplate, fail]);
  useEffect(() => {
    loadRows().catch(fail);
  }, [loadRows, fail]);

  const refreshPreview = useCallback(async () => {
    if (!layout) return;
    try {
      const blob = await apiBlobPost(`/events/${eventId}/badges/preview/`, {
        layout,
        name_source: nameSource,
        attendee: previewFor.current,
      });
      setPreview((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(blob);
      });
    } catch (e) {
      fail(e);
    }
  }, [eventId, layout, nameSource, fail]);

  useEffect(() => {
    const h = setTimeout(refreshPreview, 400);
    return () => clearTimeout(h);
  }, [refreshPreview, tpl]);

  // Опрос фоновой задачи, пока она не завершится.
  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const h = setTimeout(async () => {
      try {
        const next = await api<JobInfo>(`/jobs/${job.id}/`);
        setJob(next);
        if (next.status === "completed") loadRows();
      } catch (e) {
        fail(e);
      }
    }, 1500);
    return () => clearTimeout(h);
  }, [job, loadRows, fail]);

  const setNum = (section: keyof BadgeLayout, key: string, value: string) =>
    setLayout((l) => (l ? { ...l, [section]: { ...l[section], [key]: value === "" ? "" : Number(value) } } : l));

  const saveTemplate = async () => {
    const body = new FormData();
    body.set("layout", JSON.stringify(layout));
    body.set("name_source", nameSource);
    if (bg) body.set("background", bg);
    try {
      const data = await api<BadgeTemplateInfo>(`/events/${eventId}/badge-template/`, { method: "PUT", body });
      setTpl(data);
      setBg(null);
      setNotice({ ok: true, text: t("Шаблон бейджа сохранён") });
    } catch (e) {
      fail(e);
    }
  };

  const resetTemplate = async () => {
    try {
      const data = await api<BadgeTemplateInfo>(`/events/${eventId}/badge-template/`, { method: "DELETE" });
      setTpl(data);
      setLayout(data.layout);
      setNameSource(data.name_source);
      setNotice({ ok: true, text: t("Используется стандартный шаблон") });
    } catch (e) {
      fail(e);
    }
  };

  const printOne = async (c: BadgeCandidate) => {
    try {
      await download(`/events/${eventId}/attendees/${c.id}/badge.pdf`, `badge_${c.id}.pdf`);
      await loadRows();
    } catch (e) {
      fail(e);
    }
  };

  const printBatch = async (ids: number[] | null) => {
    try {
      setJob(await api<JobInfo>(`/events/${eventId}/badges/`, { method: "POST", body: ids ? { attendee_ids: ids } : {} }));
      setNotice(null);
    } catch (e) {
      fail(e);
    }
  };

  const selectable = useMemo(() => (rows || []).filter((r) => r.access_status === "yes"), [rows]);
  const toggle = (id: number) =>
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  if (!tpl || !layout) return notice ? <Notice value={notice} /> : <Spinner />;

  return (
    <div>
      <PageHeader title={t("Бейджи")} subtitle={t("Печатаются только участники с разрешённым доступом по результату проверки СГО.")} />
      <Notice value={notice} />
      {!tpl.font_ok && (
        <p role="alert" className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          {t("На сервере не найден шрифт с казахскими буквами — ФИО может напечататься с пропусками. Укажите BADGE_FONT_PATH.")}
        </p>
      )}

      <section className="card mb-8 p-5" aria-labelledby="tpl">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 id="tpl" className="text-lg font-semibold">
            {t("Шаблон бейджа")} {tpl.is_default && <Badge color="gray">{t("стандартный")}</Badge>}
          </h2>
          <div className="flex gap-2">
            <button type="button" className="btn-primary" onClick={saveTemplate}>
              {t("Сохранить шаблон")}
            </button>
            {!tpl.is_default && (
              <ConfirmButton className="btn-secondary" question={t("Вернуть стандартный фон и разметку?")} onConfirm={resetTemplate}>
                {t("Сбросить")}
              </ConfirmButton>
            )}
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="space-y-4">
            <label className="block">
              <span className="label">{t("Фон (PNG или JPEG, пропорции карточки, до 5 МБ)")}</span>
              <input type="file" accept=".png,.jpg,.jpeg" className="input py-1.5 text-xs" onChange={(e) => setBg(e.target.files?.[0] || null)} />
              <span className="mt-1 block text-xs text-slate-500">
                {tpl.has_background ? t("Загружен свой фон. Новый файл заменит его.") : t("Сейчас стандартный фон.")}{" "}
                {t("Сменили фон — перемерьте разметку.")}
              </span>
            </label>
            <label className="block">
              <span className="label">{t("Какое имя печатать")}</span>
              <select className="input" value={nameSource} onChange={(e) => setNameSource(e.target.value as "ru" | "latin")}>
                <option value="ru">{t("Фамилия Имя")}</option>
                <option value="latin">{t("Транслитерация")}</option>
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              {NUMBERS.map(([section, key, label, step]) => (
                <label key={`${section}.${key}`} className="block">
                  <span className="label text-xs">{t(label)}</span>
                  <input
                    type="number"
                    step={step ?? 0.1}
                    className="input"
                    value={String((layout[section] as Record<string, number | string>)[key] ?? "")}
                    onChange={(e) => setNum(section, key, e.target.value)}
                  />
                </label>
              ))}
            </div>
          </div>
          <div>
            <p className="label">{t("Предпросмотр")}</p>
            {preview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview} alt={t("Предпросмотр бейджа")} className="w-full rounded-lg border border-slate-200" />
            ) : (
              <Spinner />
            )}
            <p className="mt-2 text-xs text-slate-500">
              {t("Предпросмотр показывает несохранённую разметку. Для предпросмотра конкретного участника нажмите «Показать» в списке.")}
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="print">
        <h2 id="print" className="mb-3 text-lg font-semibold">
          {t("Печать")}
        </h2>
        {job && (
          <div className="card mb-4 p-4" role="status">
            {job.status === "completed" ? (
              <div className="space-y-2">
                <p className="font-medium text-green-700">
                  {t("PDF готов: {n} бейджей", { n: job.result?.badge_count ?? 0 })}
                </p>
                <button type="button" className="btn-primary" onClick={() => download(`/jobs/${job.id}/file/`, job.result?.file_name || `badges_${job.id}.pdf`).catch(fail)}>
                  {t("Скачать PDF")}
                </button>
                {!!job.result?.warnings.length && (
                  <ul className="list-disc pl-5 text-sm text-amber-800">
                    {job.result.warnings.map((w, i) => (
                      <li key={i}>
                        {w.problem === "no_photo" ? t("{name}: нет фото — напечатана заглушка", { name: w.name }) : t("Не найден шрифт с казахскими буквами")}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : job.status === "failed" ? (
              <p className="text-red-700">
                {t("Задача не выполнена")}: {job.error}
              </p>
            ) : (
              <div>
                <p className="mb-2 text-sm">
                  {t("Готовим PDF…")} {job.progress}%
                </p>
                <div className="h-2 overflow-hidden rounded bg-slate-200">
                  <div className="h-full bg-brand-600 transition-all" style={{ width: `${Math.max(5, job.progress)}%` }} />
                </div>
              </div>
            )}
          </div>
        )}
        <div className="card mb-3 flex flex-wrap items-end gap-3 p-4">
          <label>
            <span className="label">{t("Доступ")}</span>
            <select className="input" value={access} onChange={(e) => setAccess(e.target.value)}>
              <option value="yes">{t("Доступ разрешён")}</option>
              <option value="no">{t("Доступ запрещён")}</option>
              <option value="none">{t("Не определён")}</option>
              <option value="">{t("Все")}</option>
            </select>
          </label>
          <label>
            <span className="label">{t("Бейдж")}</span>
            <select className="input" value={printed} onChange={(e) => setPrinted(e.target.value)}>
              <option value="false">{t("Ещё не печатался")}</option>
              <option value="true">{t("Уже печатался")}</option>
              <option value="">{t("Все")}</option>
            </select>
          </label>
          <label className="min-w-48 flex-1">
            <span className="label">{t("Поиск")}</span>
            <input className="input" type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <button type="button" className="btn-primary" disabled={!selected.size} onClick={() => printBatch(Array.from(selected))}>
            {t("Печать выбранных ({n})", { n: selected.size })}
          </button>
          <button type="button" className="btn-secondary" onClick={() => printBatch(null)}>
            {t("Печать всех, кому ещё не печатали")}
          </button>
        </div>
        {!rows ? (
          <Spinner />
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-600">
                <tr>
                  <th className="p-3">
                    <input
                      type="checkbox"
                      aria-label={t("Выбрать всех")}
                      checked={selectable.length > 0 && selectable.every((r) => selected.has(r.id))}
                      onChange={(e) => setSelected(e.target.checked ? new Set(selectable.map((r) => r.id)) : new Set())}
                    />
                  </th>
                  <th className="p-3">{t("Участник")}</th>
                  <th className="p-3">{t("Заявка")}</th>
                  <th className="p-3">{t("Доступ")}</th>
                  <th className="p-3">{t("Бейдж напечатан")}</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="p-3">
                      <input type="checkbox" disabled={r.access_status !== "yes"} checked={selected.has(r.id)} onChange={() => toggle(r.id)} aria-label={r.name} />
                    </td>
                    <td className="p-3">
                      <div className="font-medium">{r.name}</div>
                      <div className="text-xs text-slate-500">
                        {r.transcription}
                        {!r.has_photo && <span className="ml-2 text-amber-700">{t("нет фото")}</span>}
                      </div>
                    </td>
                    <td className="p-3 text-slate-600">{r.request_name}</td>
                    <td className="p-3">
                      {r.access_status === "yes" ? (
                        <Badge color="green">{t("разрешён")}</Badge>
                      ) : r.access_status === "no" ? (
                        <Badge color="red">{t("запрещён")}</Badge>
                      ) : (
                        <Badge color="gray">{t("не определён")}</Badge>
                      )}
                    </td>
                    <td className="p-3 text-slate-600">{r.badge_printed_at ? formatDateTime(r.badge_printed_at) : "—"}</td>
                    <td className="space-x-1 whitespace-nowrap p-3 text-right">
                      <button
                        type="button"
                        className="btn-ghost px-2 py-1 text-xs"
                        onClick={() => {
                          previewFor.current = r.id;
                          refreshPreview();
                          window.scrollTo({ top: 0, behavior: "smooth" });
                        }}
                      >
                        {t("Показать")}
                      </button>
                      {r.access_status === "yes" && (
                        <button type="button" className="btn-secondary px-2 py-1 text-xs" onClick={() => printOne(r)}>
                          {t("Бейдж")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <p className="p-6 text-center text-slate-500">{t("Никого не найдено")}</p>}
          </div>
        )}
      </section>
    </div>
  );
}

export default function Page() {
  const { eventId } = useParams<{ eventId: string }>();
  return (
    <StaffShell eventId={eventId}>
      <BadgesPage eventId={eventId} />
    </StaffShell>
  );
}
