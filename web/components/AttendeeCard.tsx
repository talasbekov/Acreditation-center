"use client";

import { mediaPath } from "@/lib/api";
import { dirName } from "@/lib/directories";
import { attendeeStateKey, STATUS_TONE, useLang } from "@/lib/i18n";
import type { Attendee, Directories } from "@/lib/types";
import { Badge, formatDate } from "./ui";

/** Карточка участника — как блок `<article>` в `request.html`. */
export default function AttendeeCard({
  a,
  dirs,
  actions,
}: {
  a: Attendee;
  dirs: Directories | null;
  actions?: React.ReactNode;
}) {
  const { t, status } = useLang();
  const key = attendeeStateKey(a);
  const photo = mediaPath(a.photo);
  const scan = mediaPath(a.docScan);
  const facts: [string, string | null | undefined, boolean?][] = [
    [t("Дата рождения:"), formatDate(a.birthDate), true],
    [t("ИИН:"), a.iin],
    [t("Гражданство:"), dirName(dirs?.countries, a.countryId)],
    [t("Пол:"), dirName(dirs?.sexes, a.sexId)],
    [t("Должность:"), a.post, true],
    [t("Объекты:"), a.visitObjects, true],
    [t("Категория:"), dirName(dirs?.categories, a.stickId)],
    [t("Тип документа:"), dirName(dirs?.document_types, a.docTypeId)],
    [t("Серия:"), a.docSeries],
    [t("Номер документа:"), a.docNumber, true],
    [t("Дата выдачи:"), formatDate(a.docBegin), true],
    [t("Действителен до:"), formatDate(a.docEnd), true],
    [t("Кем выдан:"), a.docIssue],
  ];

  return (
    <article className="card p-5" aria-labelledby={`att-${a.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id={`att-${a.id}`} className="text-lg font-semibold text-slate-900">
            {a.surname} {a.firstname} {a.patronymic || ""}
          </h2>
          <p className="text-sm text-slate-500">{a.transcription}</p>
        </div>
        <Badge color={STATUS_TONE[key] || "blue"}>{status(key)}</Badge>
      </div>
      {a.status === "draft" && a.review_comment && (
        <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          <b>{status("reason")}:</b> {a.review_comment}
        </p>
      )}
      <div className="mt-4 flex flex-col gap-4 sm:flex-row">
        {(photo || scan) && (
          <div className="flex shrink-0 gap-2">
            {photo && (
              <a href={photo} target="_blank" rel="noopener noreferrer">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={photo} alt="" loading="lazy" className="h-40 w-30 rounded-lg border border-slate-200 object-cover" />
              </a>
            )}
            {scan && (
              <a href={scan} target="_blank" rel="noopener noreferrer">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={scan} alt="" loading="lazy" className="h-40 rounded-lg border border-slate-200 object-contain" />
              </a>
            )}
          </div>
        )}
        <dl className="grid flex-1 grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
          {facts
            .filter(([, value, always]) => always || value)
            .map(([label, value]) => (
              <div key={label} className="contents">
                <dt className="text-slate-500">{label}</dt>
                <dd className="text-slate-900">{value || ""}</dd>
              </div>
            ))}
        </dl>
      </div>
      {actions && <div className="mt-4 flex flex-wrap gap-2">{actions}</div>}
    </article>
  );
}
