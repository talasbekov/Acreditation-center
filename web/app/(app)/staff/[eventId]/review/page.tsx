"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiException, mediaPath } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { ReviewItem, ReviewQueue } from "@/lib/types";
import Notice, { type NoticeValue } from "@/components/Notice";
import StaffShell from "@/components/staff/StaffShell";
import { Badge, PageHeader, Spinner, formatDate } from "@/components/ui";

/** «Очередь проверки» (`/review/<event>/`): взять на проверку, допустить, вернуть с причиной. */
function ReviewPage({ eventId }: { eventId: string }) {
  const { t } = useLang();
  const [q, setQ] = useState<ReviewQueue | null>(null);
  const [notice, setNotice] = useState<NoticeValue>(null);
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [openReturn, setOpenReturn] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => setQ(await api<ReviewQueue>(`/staff/events/${eventId}/review/`)), [eventId]);
  useEffect(() => {
    load().catch(() => setNotice({ ok: false, text: t("Не удалось подключиться к серверу") }));
  }, [load, t]);

  const decide = async (a: ReviewItem, decision: "start" | "approve" | "return") => {
    setBusy(a.id);
    try {
      const r = await api<{ message: string }>(`/staff/attendees/${a.id}/${decision}/`, {
        method: "POST",
        body: decision === "return" ? { reason: reasons[a.id] || "" } : {},
      });
      setNotice({ ok: true, text: r.message });
      setOpenReturn(null);
      await load();
    } catch (e) {
      setNotice({ ok: false, text: e instanceof ApiException ? String(e.problem.detail || e.message) : t("Не удалось подключиться к серверу") });
    } finally {
      setBusy(null);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  if (!q) return notice ? <Notice value={notice} /> : <Spinner />;
  const s = q.summary;

  return (
    <div>
      <PageHeader title={t("Очередь проверки")} subtitle={q.event.name_rus || q.event.event_code} />
      <Notice value={notice} />
      <ul className="mb-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-5" aria-label={t("Сводка по статусам")}>
        {[
          [s.submitted, <Badge key="s" color="amber">{t("Ждут проверки")}</Badge>],
          [s.in_review, <Badge key="i" color="blue">{t("На проверке")}</Badge>],
          [s.returned, <Badge key="r" color="red">{t("Возвращены оператору")}</Badge>],
          [s.ready, <Badge key="d" color="green">{t("Допущены")}</Badge>],
          [s.exported, <Badge key="e" color="green">{t("Выгружены")}</Badge>],
        ].map(([n, badge], i) => (
          <li key={i} className="card p-3">
            <span className="block text-2xl font-bold">{n as number}</span>
            {badge}
          </li>
        ))}
      </ul>

      <h2 className="mb-3 text-lg font-semibold">
        {t("Участники")}
        {q.total ? ` (${q.total})` : ""}
      </h2>
      {q.items.length === 0 && <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800">{t("Нет участников, ожидающих проверки.")}</p>}
      <div className="space-y-4">
        {q.items.map((a) => {
          const photo = mediaPath(a.photo);
          const scan = mediaPath(a.docScan);
          return (
            <article key={a.id} className="card p-5" aria-labelledby={`person-${a.id}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 id={`person-${a.id}`} className="text-lg font-semibold">
                  {a.surname} {a.firstname} {a.patronymic}
                </h3>
                {a.status === "in_review" ? <Badge color="blue">{t("На проверке")}</Badge> : <Badge color="amber">{t("Ждёт проверки")}</Badge>}
              </div>
              <p className="text-sm text-slate-500">
                {t("Заявка")} {a.request_name} · {t("оператор")} {a.operator}
              </p>
              <div className="mt-3 flex flex-col gap-4 sm:flex-row">
                <div className="flex shrink-0 gap-2">
                  {photo && (
                    <a href={photo} target="_blank" rel="noopener noreferrer">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={photo} alt={t("Фото участника {name} — открыть крупно", { name: a.surname })} className="h-40 rounded-lg border object-cover" loading="lazy" />
                    </a>
                  )}
                  {scan && (
                    <a href={scan} target="_blank" rel="noopener noreferrer">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={scan} alt={t("Скан документа {name} — открыть крупно", { name: a.surname })} className="h-40 rounded-lg border object-contain" loading="lazy" />
                    </a>
                  )}
                </div>
                <dl className="grid flex-1 grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
                  <dt className="text-slate-500">{t("Латиницей")}</dt>
                  <dd>{a.transcription}</dd>
                  <dt className="text-slate-500">{t("Дата рождения")}</dt>
                  <dd>{formatDate(a.birthDate) || "—"}</dd>
                  <dt className="text-slate-500">{t("Гражданство")}</dt>
                  <dd>{a.country}</dd>
                  <dt className="text-slate-500">{t("Документ")}</dt>
                  <dd>
                    {a.doc_type} {a.docSeries} {a.docNumber}, {t("до")} {formatDate(a.docEnd) || "—"}
                  </dd>
                  <dt className="text-slate-500">{t("Должность")}</dt>
                  <dd>{a.post}</dd>
                  <dt className="text-slate-500">{t("Объекты")}</dt>
                  <dd>{a.visitObjects}</dd>
                </dl>
              </div>
              <div className="mt-4 flex flex-wrap items-start gap-2">
                {a.status === "submitted" ? (
                  <button type="button" className="btn-primary" disabled={busy === a.id} onClick={() => decide(a, "start")}>
                    {t("Взять на проверку")}
                  </button>
                ) : (
                  <>
                    <button type="button" className="btn-primary bg-green-600 hover:bg-green-700" disabled={busy === a.id} onClick={() => decide(a, "approve")}>
                      {t("Допустить")}
                    </button>
                    {openReturn === a.id ? (
                      <form
                        className="w-full space-y-2"
                        onSubmit={(e) => {
                          e.preventDefault();
                          decide(a, "return");
                        }}
                      >
                        <label className="label" htmlFor={`reason-${a.id}`}>
                          {t("Причина возврата")}
                        </label>
                        <textarea
                          id={`reason-${a.id}`}
                          className="input"
                          required
                          maxLength={q.max_reason}
                          value={reasons[a.id] || ""}
                          onChange={(e) => setReasons((r) => ({ ...r, [a.id]: e.target.value }))}
                          aria-describedby={`reason-hint-${a.id}`}
                        />
                        <p id={`reason-hint-${a.id}`} className="text-xs text-slate-500">
                          {t("Её увидит оператор. До {n} символов.", { n: q.max_reason })}
                        </p>
                        <div className="flex gap-2">
                          <button type="submit" className="btn-danger" disabled={busy === a.id}>
                            {t("Вернуть")}
                          </button>
                          <button type="button" className="btn-secondary" onClick={() => setOpenReturn(null)}>
                            {t("Отмена")}
                          </button>
                        </div>
                      </form>
                    ) : (
                      <button type="button" className="btn-danger" onClick={() => setOpenReturn(a.id)}>
                        {t("Вернуть оператору…")}
                      </button>
                    )}
                  </>
                )}
              </div>
            </article>
          );
        })}
      </div>
      {q.overflow && <p className="mt-3 text-sm text-slate-500">{t("Показаны первые {n} из {total}.", { n: q.items.length, total: q.total })}</p>}
    </div>
  );
}

export default function Page() {
  const { eventId } = useParams<{ eventId: string }>();
  return (
    <StaffShell eventId={eventId}>
      <ReviewPage eventId={eventId} />
    </StaffShell>
  );
}
