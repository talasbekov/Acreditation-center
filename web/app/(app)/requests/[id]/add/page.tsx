"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { setFlash } from "@/lib/flash";
import { useLang } from "@/lib/i18n";
import type { RequestDetail } from "@/lib/types";
import AttendeeForm from "@/components/AttendeeForm";
import { ErrorBox, PageHeader, Spinner } from "@/components/ui";

/** «Добавить участника» (`/add_attendee/<req>/`). */
export default function AddAttendeePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { t, name, msg, err, life } = useLang();
  const [req, setReq] = useState<RequestDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<RequestDetail>(`/requests/${id}/`)
      .then(setReq)
      .catch((e) => setError(e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу")));
  }, [id, err, t]);

  if (error) return <ErrorBox text={error} />;
  if (!req) return <Spinner />;
  if (!req.can_add) {
    return (
      <div>
        <PageHeader title={t("Добавить участника")} back={{ href: `/requests/${id}`, label: t("Вернуться к заявке") }} />
        <ErrorBox text={life("closed")} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        back={{ href: `/requests/${id}`, label: t("Вернуться к заявке") }}
        title={t("Добавить участника для мероприятия «{event}»", { event: name(req.event) })}
      />
      <AttendeeForm
        requestId={req.id}
        eventId={req.event.id}
        onCancel={() => router.push(`/requests/${id}`)}
        onSaved={(a) => {
          setFlash(msg("added", { surname: a.surname, firstname: a.firstname, transcription: a.transcription }));
          router.push(`/requests/${id}`);
        }}
      />
    </div>
  );
}
