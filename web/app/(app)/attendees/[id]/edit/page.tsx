"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { setFlash } from "@/lib/flash";
import { useLang } from "@/lib/i18n";
import type { Attendee, RequestDetail } from "@/lib/types";
import AttendeeForm from "@/components/AttendeeForm";
import { ErrorBox, PageHeader, Spinner } from "@/components/ui";

/**
 * «Изменить» участника (`/update_attendee/<id>/`). После сохранения — туда же, куда
 * HTML-вьюха: админ — в карточку мероприятия, супероператор с чужим участником — на
 * дашборд, оператор — на страницу заявки.
 */
export default function EditAttendeePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { me } = useAuth();
  const { t, name, err } = useLang();
  const [attendee, setAttendee] = useState<Attendee | null>(null);
  const [req, setReq] = useState<RequestDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const a = await api<Attendee>(`/attendees/${id}/`);
        setAttendee(a);
        try {
          setReq(await api<RequestDetail>(`/requests/${a.request}/`));
        } catch {
          /* чужая заявка (супероператор) — форма работает и без неё */
        }
      } catch (e) {
        setError(e instanceof ApiException ? err(e.problem) : t("Не удалось подключиться к серверу"));
      }
    })();
  }, [id, err, t]);

  if (error) return <ErrorBox text={error} />;
  if (!attendee) return <Spinner />;

  const back = () => {
    if (me?.is_superuser && req) return `/admin/events/${req.event.id}`;
    if (req && (me?.role !== "superoperator" || req.created_by.username === me.username)) return `/requests/${req.id}`;
    return req ? `/staff/${req.event.id}/dashboard` : "/cabinet";
  };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        back={{ href: back(), label: t("Вернуться к заявке") }}
        title={t("Редактировать участника для мероприятия «{event}»", { event: req ? name(req.event) : "" })}
      />
      <AttendeeForm
        requestId={attendee.request}
        attendee={attendee}
        onCancel={() => router.push(back())}
        onSaved={() => {
          setFlash(t("Изменения сохранены"));
          router.push(back());
        }}
      />
    </div>
  );
}
