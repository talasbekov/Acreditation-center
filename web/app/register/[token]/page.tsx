"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { LANGS, useLang } from "@/lib/i18n";
import type { Attendee, CustomField, Directories, EventBrief } from "@/lib/types";
import AttendeeForm from "@/components/AttendeeForm";
import { Spinner } from "@/components/ui";

interface Info {
  event: EventBrief;
  link_type: "single" | "multi";
  is_available: boolean;
  custom_fields: CustomField[];
  directories: Directories;
}

/** Публичная форма саморегистрации по ссылке оператора (без входа в систему). */
export default function RegisterPage() {
  const { token } = useParams<{ token: string }>();
  const { t, name, lang, setLang } = useLang();
  const [info, setInfo] = useState<Info | null>(null);
  const [state, setState] = useState<"loading" | "form" | "gone" | "done" | "error">("loading");
  const [doneCount, setDoneCount] = useState(0);

  useEffect(() => {
    setState("loading");
    api<Info>(`/public/register/${token}/`, { query: { lang } })
      .then((data) => {
        setInfo(data);
        setState("form");
      })
      .catch((e) => setState(e instanceof ApiException && (e.status === 410 || e.status === 404) ? "gone" : "error"));
  }, [token, lang]);

  const submit = (body: FormData) => api<Attendee>(`/public/register/${token}/`, { method: "POST", body });

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="leading-tight">
            <div className="text-sm font-bold">{t("Аккредитационный центр")}</div>
            <div className="text-xs text-slate-500">{t("Служба государственной охраны РК")}</div>
          </div>
          <div className="flex overflow-hidden rounded-lg border border-slate-200" role="group" aria-label={t("Язык")}>
            {LANGS.map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLang(l)}
                aria-pressed={lang === l}
                className={`px-2.5 py-1 text-xs font-semibold uppercase ${lang === l ? "bg-brand-600 text-white" : "bg-white text-slate-500"}`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-4 py-6">
        {state === "loading" && <Spinner />}
        {state === "gone" && (
          <p role="alert" className="card p-6 text-center text-slate-700">
            {t("Ссылка недействительна или уже использована.")}
          </p>
        )}
        {state === "error" && (
          <p role="alert" className="card p-6 text-center text-red-700">
            {t("Не удалось подключиться к серверу")}
          </p>
        )}
        {state === "done" && (
          <div role="status" className="card space-y-4 p-6 text-center">
            <p className="text-lg font-semibold text-green-700">{t("Регистрация принята")}</p>
            <p className="text-sm text-slate-600">{t("Данные переданы оператору мероприятия для проверки.")}</p>
            {info?.link_type === "multi" && (
              <button type="button" className="btn-secondary" onClick={() => setState("form")}>
                {t("Зарегистрировать ещё одного участника")}
              </button>
            )}
          </div>
        )}
        {state === "form" && info && (
          <>
            <h1 className="mb-1 text-2xl font-bold">{t("Регистрация участника")}</h1>
            <p className="mb-6 text-slate-600">{name(info.event)}</p>
            <AttendeeForm
              key={doneCount}
              directories={info.directories}
              customFields={info.custom_fields}
              submit={submit}
              submitLabel={t("Отправить")}
              onSaved={() => {
                setDoneCount((n) => n + 1);
                setState("done");
                window.scrollTo({ top: 0 });
              }}
            />
          </>
        )}
      </main>
    </div>
  );
}
