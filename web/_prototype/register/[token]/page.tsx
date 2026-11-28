"use client";

import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Spinner } from "@/components/ui";
import ParticipantForm, { type ParticipantPayload } from "@/components/ParticipantForm";
import type { CustomField } from "@/lib/types";

interface Info {
  event_name: string;
  link_type: string;
  is_available: boolean;
  custom_fields: CustomField[];
}

export default function RegisterPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const [info, setInfo] = useState<Info | null>(null);
  const [loading, setLoading] = useState(true);
  const [expired, setExpired] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    api<Info>(`/register/${token}/info`, { auth: false })
      .then(setInfo)
      .catch(() => setExpired(true))
      .finally(() => setLoading(false));
  }, [token]);

  const submit = async (payload: ParticipantPayload) => {
    await api(`/register/${token}`, { method: "POST", auth: false, body: payload });
    setDone(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-700 to-brand-900 py-10">
      <div className="mx-auto max-w-3xl px-4">
        <div className="mb-6 text-center text-white">
          <div className="mb-2 text-3xl">🛡️</div>
          <h1 className="text-xl font-bold">Центр аккредитации</h1>
        </div>

        <div className="card p-6 sm:p-8">
          {loading ? (
            <Spinner />
          ) : expired || (info && !info.is_available) ? (
            <div className="py-12 text-center">
              <div className="mb-3 text-4xl">⛔</div>
              <h2 className="text-lg font-semibold text-slate-900">Ссылка недоступна</h2>
              <p className="mt-1 text-sm text-slate-500">
                Эта ссылка регистрации использована или деактивирована.
              </p>
            </div>
          ) : done ? (
            <div className="py-12 text-center">
              <div className="mb-3 text-4xl">✅</div>
              <h2 className="text-lg font-semibold text-slate-900">Регистрация успешна</h2>
              <p className="mt-1 text-sm text-slate-500">
                Ваши данные отправлены организатору мероприятия.
              </p>
            </div>
          ) : (
            <>
              <div className="mb-6">
                <p className="text-xs uppercase tracking-wide text-brand-600">Регистрация на мероприятие</p>
                <h2 className="text-xl font-bold text-slate-900">{info?.event_name}</h2>
              </div>
              <ParticipantForm
                fields={info?.custom_fields || []}
                submitLabel="Зарегистрироваться"
                onSubmit={submit}
                onCancel={() => history.back()}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
