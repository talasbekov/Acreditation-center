"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { KZ_COUNTRY_ID, useDirectories } from "@/lib/directories";
import { useLang } from "@/lib/i18n";
import type { Attendee } from "@/lib/types";
import { ErrorBox, Field } from "./ui";

/**
 * Форма участника — поля, порядок и правила `_attendee_fields.html` старой АЦ:
 * ИИН только у граждан РК, категория только у нерезидентов, типы документов по
 * гражданству (РК: удостоверение и паспорт РК; иначе — иностранные), транслитерация
 * только латиницей, при добавлении фото и скан обязательны и даты ограничены сегодняшним днём.
 * Полную проверку (ИИН, даты, файлы, дубли) делает сервер теми же валидаторами.
 */

const KZ_DOCS = ["1000000001", "1000000003"];
const FOREIGN_DOCS = ["1000000002", "1000000004", "1000000005"];
const PHOTO_EXT = [".jpg", ".jpeg", ".png", ".webp"];
const SCAN_EXT = [...PHOTO_EXT, ".pdf"];

type Values = {
  surname: string;
  firstname: string;
  patronymic: string;
  transcription: string;
  birthDate: string;
  sexId: string;
  post: string;
  countryId: string;
  iin: string;
  stickId: string;
  docTypeId: string;
  docSeries: string;
  docNumber: string;
  docIssue: string;
  docBegin: string;
  docEnd: string;
  visitObjects: string;
};

const EMPTY: Values = {
  surname: "",
  firstname: "",
  patronymic: "",
  transcription: "",
  birthDate: "",
  sexId: "",
  post: "",
  countryId: KZ_COUNTRY_ID,
  iin: "",
  stickId: "",
  docTypeId: "1000000003",
  docSeries: "",
  docNumber: "",
  docIssue: "",
  docBegin: "",
  docEnd: "",
  visitObjects: "",
};

function fromAttendee(a: Attendee): Values {
  return {
    surname: a.surname || "",
    firstname: a.firstname || "",
    patronymic: a.patronymic || "",
    transcription: a.transcription || "",
    birthDate: a.birthDate || "",
    sexId: a.sexId || "",
    post: a.post || "",
    countryId: a.countryId || KZ_COUNTRY_ID,
    iin: a.iin || "",
    stickId: a.stickId || "",
    docTypeId: a.docTypeId || "",
    docSeries: a.docSeries || "",
    docNumber: a.docNumber || "",
    docIssue: a.docIssue || "",
    docBegin: a.docBegin || "",
    docEnd: a.docEnd || "",
    visitObjects: a.visitObjects || "",
  };
}

function today() {
  const d = new Date();
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
}

export default function AttendeeForm({
  requestId,
  attendee,
  onSaved,
  onCancel,
}: {
  requestId: number;
  attendee?: Attendee;
  onSaved: (a: Attendee) => void;
  onCancel: () => void;
}) {
  const { t, err } = useLang();
  const dirs = useDirectories();
  const mode = attendee ? "edit" : "add";
  const [v, setV] = useState<Values>(attendee ? fromAttendee(attendee) : EMPTY);
  const [photo, setPhoto] = useState<File | null>(null);
  const [scan, setScan] = useState<File | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const resident = v.countryId === KZ_COUNTRY_ID;
  const maxDate = today();

  const set = (k: keyof Values) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setV((s) => ({ ...s, [k]: e.target.value }));

  // Первый пол по умолчанию — как первый <option> в шаблоне.
  useEffect(() => {
    if (dirs && !v.sexId && dirs.sexes.length) setV((s) => ({ ...s, sexId: dirs.sexes[0].code }));
    if (dirs && !resident && !v.stickId && dirs.categories.length) setV((s) => ({ ...s, stickId: dirs.categories[0].code }));
  }, [dirs, v.sexId, v.stickId, resident]);

  const docTypes = useMemo(() => {
    const all = dirs?.document_types || [];
    const allowed = resident ? KZ_DOCS : FOREIGN_DOCS;
    const rows = all.filter((d) => allowed.includes(d.code));
    return rows.length ? rows : all;
  }, [dirs, resident]);

  // Смена гражданства: ИИН нерезидента не отправляется, тип документа — из разрешённых.
  const changeCountry = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const countryId = e.target.value;
    const isKz = countryId === KZ_COUNTRY_ID;
    const allowed = isKz ? KZ_DOCS : FOREIGN_DOCS;
    setV((s) => ({
      ...s,
      countryId,
      iin: isKz ? s.iin : "",
      docTypeId: allowed.includes(s.docTypeId) ? s.docTypeId : isKz ? "1000000003" : "1000000002",
    }));
  };

  const pickFile = (exts: string[], setter: (f: File | null) => void) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    if (file && !exts.some((x) => file.name.toLowerCase().endsWith(x))) {
      setError(t("Недопустимый файл. Допустимые форматы: ") + exts.join(", "));
      e.target.value = "";
      setter(null);
      return;
    }
    setError("");
    setter(file);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrors({});
    setError("");
    const body = new FormData();
    body.set("request", String(requestId));
    for (const [k, val] of Object.entries(v)) {
      if (k === "iin" && !resident) continue;
      if (k === "stickId" && resident) continue;
      body.set(k, val);
    }
    if (photo) body.set("photo", photo);
    if (scan) body.set("docScan", scan);
    try {
      const saved = attendee
        ? await api<Attendee>(`/attendees/${attendee.id}/`, { method: "PATCH", body })
        : await api<Attendee>("/attendees/", { method: "POST", body });
      onSaved(saved);
    } catch (ex) {
      if (ex instanceof ApiException) {
        const text = err(ex.problem);
        const field = ex.problem.field || undefined;
        if (field) setErrors({ [field]: text });
        setError(text);
      } else setError(t("Не удалось подключиться к серверу"));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setSaving(false);
    }
  };

  if (!dirs) return null;

  const input = (k: keyof Values, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <input
      id={k}
      className="input"
      value={v[k]}
      onChange={set(k)}
      aria-invalid={errors[k] ? true : undefined}
      {...extra}
    />
  );

  return (
    <form onSubmit={submit} className="space-y-6" noValidate={false}>
      <ErrorBox text={error} />
      <p className="text-sm text-slate-500">{t("Поля со звёздочкой * обязательны.")}</p>

      <section className="card p-5" aria-labelledby="sec-main">
        <h2 id="sec-main" className="mb-4 text-base font-semibold">
          {t("Основные сведения")}
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("Фамилия")} required error={errors.surname} htmlFor="surname">
            {input("surname", { required: true })}
          </Field>
          <Field label={t("Имя")} required error={errors.firstname} htmlFor="firstname">
            {input("firstname", { required: true })}
          </Field>
          <Field label={t("Отчество")} error={errors.patronymic} htmlFor="patronymic">
            {input("patronymic")}
          </Field>
          <Field label={t("Транслитерация полного имени")} required error={errors.transcription} htmlFor="transcription">
            <input
              id="transcription"
              className="input"
              required
              placeholder="Aliev Ali"
              value={v.transcription}
              onChange={(e) => setV((s) => ({ ...s, transcription: e.target.value.replace(/[^A-Za-z\s]/g, "") }))}
            />
          </Field>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Field label={t("Дата рождения")} required error={errors.birthDate} htmlFor="birthDate">
            {input("birthDate", { type: "date", required: true, min: "1930-01-01", max: maxDate })}
          </Field>
          <Field label={t("Пол")} required error={errors.sexId} htmlFor="sexId">
            <select id="sexId" className="input" required value={v.sexId} onChange={set("sexId")}>
              {dirs.sexes.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("Должность")} required error={errors.post} htmlFor="post">
            {input("post", { required: true })}
          </Field>
        </div>
      </section>

      <section className="card p-5" aria-labelledby="sec-citizenship">
        <h2 id="sec-citizenship" className="mb-4 text-base font-semibold">
          {t("Гражданство")}
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("Гражданство")} required error={errors.countryId} htmlFor="countryId">
            <select id="countryId" className="input" required value={v.countryId} onChange={changeCountry}>
              {dirs.countries.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
          </Field>
          {resident ? (
            <Field label={t("ИИН")} required error={errors.iin} htmlFor="iin">
              <input
                id="iin"
                className="input"
                inputMode="numeric"
                required
                minLength={12}
                maxLength={12}
                value={v.iin}
                aria-invalid={errors.iin ? true : undefined}
                onChange={(e) => setV((s) => ({ ...s, iin: e.target.value.replace(/[^0-9]/g, "") }))}
              />
              {v.iin.length === 12 && !errors.iin && (
                <p role="status" className="mt-1 text-xs text-green-700">
                  {t("✅ Формат ИИН верный")}
                </p>
              )}
            </Field>
          ) : (
            <Field label={t("Категория")} required error={errors.stickId} htmlFor="stickId">
              <select id="stickId" className="input" required value={v.stickId} onChange={set("stickId")}>
                {dirs.categories.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
        </div>
      </section>

      <section className="card p-5" aria-labelledby="sec-doc">
        <h2 id="sec-doc" className="mb-4 text-base font-semibold">
          {t("Документ")}
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("Тип документа")} required error={errors.docTypeId} htmlFor="docTypeId">
            <select id="docTypeId" className="input" required value={v.docTypeId} onChange={set("docTypeId")}>
              {docTypes.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("Серия")} error={errors.docSeries} htmlFor="docSeries">
            {input("docSeries")}
          </Field>
          <Field label={t("Номер документа")} required error={errors.docNumber} htmlFor="docNumber">
            {input("docNumber", { required: true })}
          </Field>
          <Field label={t("Кем выдан")} error={errors.docIssue} htmlFor="docIssue">
            {input("docIssue")}
          </Field>
          <Field label={t("Дата выдачи")} required error={errors.docBegin} htmlFor="docBegin">
            {input("docBegin", { type: "date", required: true, ...(mode === "add" ? { max: maxDate } : {}) })}
          </Field>
          <Field label={t("Действителен до")} required error={errors.docEnd} htmlFor="docEnd">
            {input("docEnd", { type: "date", required: true, ...(mode === "add" ? { min: maxDate } : {}) })}
          </Field>
        </div>
      </section>

      <section className="card p-5" aria-labelledby="sec-visit">
        <h2 id="sec-visit" className="mb-4 text-base font-semibold">
          {t("Посещение и файлы")}
        </h2>
        <Field label={t("Планируемые объекты посещения")} required error={errors.visitObjects} htmlFor="visitObjects">
          <textarea id="visitObjects" className="input" rows={3} required value={v.visitObjects} onChange={set("visitObjects")} />
        </Field>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field
            label={
              mode === "edit"
                ? t("Новое фото участника — только если нужно заменить: JPG, PNG или WEBP, вертикальное 3×4, не меньше 600×800, до 5 МБ")
                : t("Фото участника: JPG, PNG или WEBP, вертикальное 3×4, не меньше 600×800, до 5 МБ")
            }
            required={mode === "add"}
            error={errors.photo}
            htmlFor="photo"
          >
            <input
              id="photo"
              type="file"
              className="input py-1.5 text-xs"
              accept={PHOTO_EXT.join(",")}
              required={mode === "add"}
              onChange={pickFile(PHOTO_EXT, setPhoto)}
            />
          </Field>
          <Field
            label={
              mode === "edit"
                ? t("Новый скан документа — только если нужно заменить: JPG, PNG, WEBP или PDF, вертикальный, не меньше 600×800, до 5 МБ")
                : t("Скан документа: JPG, PNG, WEBP или PDF, вертикальный, не меньше 600×800, до 5 МБ")
            }
            required={mode === "add"}
            error={errors.docScan}
            htmlFor="docScan"
          >
            <input
              id="docScan"
              type="file"
              className="input py-1.5 text-xs"
              accept={SCAN_EXT.join(",")}
              required={mode === "add"}
              onChange={pickFile(SCAN_EXT, setScan)}
            />
          </Field>
        </div>
      </section>

      {mode === "add" && (
        <p className="text-sm text-slate-600">
          {t(
            "При добавлении участника Вы соглашаетесь на обработку и хранение персональных данных в информационных системах СГО РК",
          )}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="btn-primary" disabled={saving}>
          {mode === "edit" ? t("Сохранить изменения") : t("Добавить участника")}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel}>
          {t("Отмена")}
        </button>
      </div>
    </form>
  );
}
