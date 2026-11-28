"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { ApiTokenRow } from "@/lib/types";
import Notice, { type NoticeValue } from "../Notice";
import { Badge, ConfirmButton, EmptyState, Field, formatDateTime } from "../ui";

/** API-токены внешних систем регистрации. Токен показывается один раз при создании. */
export default function TokensTab({ eventId }: { eventId: string }) {
  const { t, err } = useLang();
  const [tokens, setTokens] = useState<ApiTokenRow[]>([]);
  const [name, setName] = useState("");
  const [fresh, setFresh] = useState<ApiTokenRow | null>(null);
  const [notice, setNotice] = useState<NoticeValue>(null);

  const load = useCallback(async () => {
    setTokens((await api<{ results: ApiTokenRow[] }>(`/events/${eventId}/api-tokens/`)).results);
  }, [eventId]);
  useEffect(() => {
    load();
  }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setFresh(await api<ApiTokenRow>(`/events/${eventId}/api-tokens/`, { method: "POST", body: { name } }));
      setName("");
      await load();
    } catch (ex) {
      setNotice({ ok: false, text: ex instanceof ApiException ? err(ex.problem) : t("Не удалось подключиться к серверу") });
    }
  };

  const disable = async (row: ApiTokenRow) => {
    await api(`/api-tokens/${row.id}/`, { method: "DELETE" });
    await load();
  };

  const origin = typeof window === "undefined" ? "" : window.location.origin;

  return (
    <div className="space-y-6">
      <Notice value={notice} />
      {fresh?.token && (
        <div className="card border-amber-300 bg-amber-50 p-5 text-sm">
          <p className="mb-2 font-semibold text-amber-900">{t("Сохраните токен сейчас — повторно он не показывается.")}</p>
          <code className="block break-all rounded bg-white p-2">{fresh.token}</code>
          <p className="mt-3 text-slate-700">{t("Запрос внешней системы:")}</p>
          <pre className="mt-1 overflow-x-auto rounded bg-white p-2 text-xs">{`POST ${origin}${fresh.endpoint}
Authorization: Bearer <токен>
Content-Type: multipart/form-data

surname, firstname, patronymic, transcription, birthDate (ГГГГ-ММ-ДД), sexId, countryId, iin,
post, docTypeId, docSeries, docNumber, docBegin, docEnd, docIssue, visitObjects, stickId,
photo (файл), docScan (файл), custom_field_values (JSON {"<id поля>": "значение"})`}</pre>
          <button type="button" className="btn-secondary mt-3" onClick={() => setFresh(null)}>
            {t("Я сохранил токен")}
          </button>
        </div>
      )}
      <form onSubmit={create} className="card flex flex-wrap items-end gap-4 p-5">
        <Field label={t("Название системы")} htmlFor="tk-name">
          <input id="tk-name" className="input" maxLength={255} value={name} onChange={(e) => setName(e.target.value)} placeholder="KazExpo" />
        </Field>
        <button type="submit" className="btn-primary">
          {t("Создать токен")}
        </button>
      </form>
      {tokens.length === 0 ? (
        <EmptyState text={t("Токенов пока нет")} />
      ) : (
        <ul className="card divide-y divide-slate-100">
          {tokens.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
              <span className="font-medium">{row.name || "—"}</span>
              <code className="text-xs text-slate-500">{row.token_prefix}…</code>
              {row.is_active ? <Badge color="green">{t("Активен")}</Badge> : <Badge color="gray">{t("Отключён")}</Badge>}
              <span className="text-xs text-slate-500">
                {t("Последний запрос")}: {row.last_used_at ? formatDateTime(row.last_used_at) : "—"}
              </span>
              <Link href={`/requests/${row.request_id}`} className="text-xs text-brand-700 hover:underline">
                {t("Заявка")}
              </Link>
              {row.is_active && (
                <ConfirmButton className="btn-ghost ml-auto px-2 py-1 text-xs text-red-700" question={t("Отключить токен? Внешняя система больше не сможет регистрировать участников.")} onConfirm={() => disable(row)}>
                  {t("Отключить")}
                </ConfirmButton>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
