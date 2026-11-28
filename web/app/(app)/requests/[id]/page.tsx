"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useDirectories } from "@/lib/directories";
import { takeFlash } from "@/lib/flash";
import { useLang } from "@/lib/i18n";
import type { Attendee, RequestDetail, SendProblem } from "@/lib/types";
import AttendeeCard from "@/components/AttendeeCard";
import { ConfirmButton, PageHeader, Spinner, formatDateTime } from "@/components/ui";

/**
 * Страница заявки (`/show/<id>/`, `/preview/<id>/`): участники, «Добавить участника»,
 * «Предпросмотр» → «Отправить», правка и удаление черновиков.
 */
function RequestPage() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const { me } = useAuth();
  const { t, name, msg, err, life } = useLang();
  const dirs = useDirectories();
  const [req, setReq] = useState<RequestDetail | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "bad"; text: string } | null>(null);
  const [problems, setProblems] = useState<SendProblem[]>([]);
  const [gone, setGone] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const preview = search.get("preview") === "1" && !!req?.can_preview;

  const load = useCallback(async () => {
    try {
      const data = await api<RequestDetail>(`/requests/${params.id}/`);
      setReq(data);
      return data;
    } catch (e) {
      if (e instanceof ApiException && e.status === 404) setGone(t("Заявка не найдена"));
      else setNotice({ kind: "bad", text: e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу") });
      return null;
    }
  }, [params.id, t, err]);

  useEffect(() => {
    load().then((data) => {
      if (data?.status === "Sent") setNotice({ kind: "ok", text: msg("sent_at", { time: formatDateTime(data.registration_time) }) });
      const flash = takeFlash();
      if (flash) setNotice({ kind: "ok", text: flash });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  useEffect(() => {
    if (preview) setNotice({ kind: "ok", text: msg("ready_to_send") });
  }, [preview, msg]);

  const setPreview = (on: boolean) => router.replace(`/requests/${params.id}${on ? "?preview=1" : ""}`);

  const send = async () => {
    setSending(true);
    setProblems([]);
    try {
      const data = await api<RequestDetail>(`/requests/${params.id}/send/`, { method: "POST" });
      setReq(data);
      router.replace(`/requests/${params.id}`);
      setNotice({ kind: "ok", text: msg("sent_at", { time: formatDateTime(data.registration_time) }) });
    } catch (e) {
      if (e instanceof ApiException) {
        const p = e.problem;
        const list = (p.problems as SendProblem[] | undefined) || [];
        setProblems(list);
        setNotice({
          kind: "bad",
          text: list.length ? life("not_ready") : p.type === "request_empty" ? life("empty") : err(p),
        });
      } else setNotice({ kind: "bad", text: t("Не удалось подключиться к серверу") });
    } finally {
      setSending(false);
    }
  };

  const remove = async (a: Attendee) => {
    try {
      await api(`/attendees/${a.id}/`, { method: "DELETE" });
    } catch (e) {
      setNotice({ kind: "bad", text: e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу") });
      return;
    }
    const data = await load();
    if (!data && req) {
      setGone(msg("request_deleted", { name: req.name }));
    } else {
      setNotice({ kind: "bad", text: msg("deleted", { surname: a.surname, firstname: a.firstname }) });
    }
  };

  if (gone) {
    return (
      <div>
        <PageHeader title={t("Заявка")} back={{ href: "/cabinet", label: t("На главную") }} />
        <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          {gone}
        </p>
      </div>
    );
  }
  if (!req) return <Spinner />;

  const editable = req.status === "Active" || req.status === "Checking";
  const fullName = me ? [me.first_name, me.last_name].filter(Boolean).join(" ") || me.username : "";
  const backHref = me?.is_superuser ? `/admin/events/${req.event.id}` : "/cabinet";

  return (
    <div>
      <PageHeader
        back={{ href: backHref, label: t("На главную") }}
        title={t("Заявка ({req}) на мероприятие {event}, в заявке {count} участников", {
          req: req.name,
          event: name(req.event),
          count: req.attendees.length,
        })}
        subtitle={t("Добро пожаловать, {name}", { name: fullName })}
      />
      {notice && (
        <div
          role={notice.kind === "ok" ? "status" : "alert"}
          className={`mb-4 rounded-lg px-3 py-2 text-sm ${notice.kind === "ok" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}
        >
          {notice.text}
          {problems.length > 0 && (
            <ul className="mt-1 list-disc pl-5">
              {problems.map((p) => (
                <li key={p.attendee_id}>
                  {p.name}: {p.codes.map((c) => life(c)).join(", ")}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {preview && (
        <p role="alert" className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {msg("send_warning")}
        </p>
      )}
      <div className="mb-6 flex flex-wrap gap-2">
        {preview ? (
          <button type="button" className="btn-secondary" onClick={() => setPreview(false)}>
            {t("Вернуться к редактированию")}
          </button>
        ) : (
          editable && (
            <Link href={`/requests/${req.id}/add`} className="btn-primary">
              {t("Добавить участника")}
            </Link>
          )
        )}
        {req.attendees.length > 0 &&
          editable &&
          (preview ? (
            <button type="button" className="btn-primary bg-green-600 hover:bg-green-700" onClick={send} disabled={sending}>
              {t("Отправить")}
            </button>
          ) : (
            <button type="button" className="btn-secondary" onClick={() => setPreview(true)}>
              {t("Предпросмотр")}
            </button>
          ))}
      </div>
      <div className="space-y-4">
        {req.attendees.map((a) => (
          <AttendeeCard
            key={a.id}
            a={a}
            dirs={dirs}
            actions={
              a.status === "draft" && !preview ? (
                <>
                  <Link href={`/attendees/${a.id}/edit`} className="btn-secondary">
                    {t("Изменить")}
                  </Link>
                  <ConfirmButton
                    question={t("Удалить участника {name}?", { name: `${a.surname} ${a.firstname}` })}
                    onConfirm={() => remove(a)}
                  >
                    {t("Удалить")}
                  </ConfirmButton>
                </>
              ) : null
            }
          />
        ))}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <RequestPage />
    </Suspense>
  );
}
