"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiException } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { RegistrationLinkRow } from "@/lib/types";
import Notice, { type NoticeValue } from "../Notice";
import { Badge, ConfirmButton, EmptyState, Field, formatDateTime } from "../ui";

/**
 * Ссылки саморегистрации: одноразовые (по одной на человека) и многоразовая.
 * Участники по ссылкам попадают черновиками в отдельную заявку оператора.
 */
export default function LinksTab({ eventId }: { eventId: string }) {
  const { t, err } = useLang();
  const [links, setLinks] = useState<RegistrationLinkRow[]>([]);
  const [notice, setNotice] = useState<NoticeValue>(null);
  const [type, setType] = useState<"single" | "multi">("single");
  const [count, setCount] = useState(1);

  const load = useCallback(async () => {
    setLinks((await api<{ results: RegistrationLinkRow[] }>(`/events/${eventId}/registration-links/`)).results);
  }, [eventId]);
  useEffect(() => {
    load();
  }, [load]);

  const abs = (url: string) => (typeof window === "undefined" ? url : window.location.origin + url);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api(`/events/${eventId}/registration-links/`, { method: "POST", body: { link_type: type, count } });
      setNotice({ ok: true, text: t("Ссылки созданы") });
      await load();
    } catch (ex) {
      setNotice({ ok: false, text: ex instanceof ApiException ? err(ex.problem) : t("Не удалось подключиться к серверу") });
    }
  };

  const disable = async (l: RegistrationLinkRow) => {
    await api(`/registration-links/${l.id}/`, { method: "DELETE" });
    await load();
  };

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setNotice({ ok: true, text: t("Скопировано") });
    } catch {
      setNotice({ ok: false, text: text });
    }
  };

  const available = links.filter((l) => l.is_available);

  return (
    <div className="space-y-6">
      <Notice value={notice} />
      <form onSubmit={create} className="card flex flex-wrap items-end gap-4 p-5">
        <Field label={t("Тип ссылки")} htmlFor="lk-type">
          <select id="lk-type" className="input" value={type} onChange={(e) => setType(e.target.value as "single" | "multi")}>
            <option value="single">{t("Одноразовая — для одного человека")}</option>
            <option value="multi">{t("Многоразовая — открытая регистрация")}</option>
          </select>
        </Field>
        {type === "single" && (
          <Field label={t("Сколько ссылок")} htmlFor="lk-count">
            <input id="lk-count" type="number" min={1} max={500} className="input w-28" value={count} onChange={(e) => setCount(Number(e.target.value))} />
          </Field>
        )}
        <button type="submit" className="btn-primary">
          {t("Создать")}
        </button>
        {available.length > 1 && (
          <button type="button" className="btn-secondary" onClick={() => copy(available.map((l) => abs(l.url)).join("\n"))}>
            {t("Скопировать все доступные ({n})", { n: available.length })}
          </button>
        )}
      </form>
      {links.length === 0 ? (
        <EmptyState text={t("Ссылок пока нет")} />
      ) : (
        <ul className="card divide-y divide-slate-100">
          {links.map((l) => (
            <li key={l.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
              <Badge color={l.link_type === "single" ? "blue" : "amber"}>{l.link_type === "single" ? t("Одноразовая") : t("Многоразовая")}</Badge>
              {l.is_available ? <Badge color="green">{t("Активна")}</Badge> : <Badge color="gray">{l.is_used ? t("Использована") : t("Отключена")}</Badge>}
              <code className="min-w-0 flex-1 truncate text-xs text-slate-600">{abs(l.url)}</code>
              <span className="text-xs text-slate-500">
                {t("Регистраций")}: {l.used_count} · {formatDateTime(l.created_at)}
              </span>
              <Link href={`/requests/${l.request_id}`} className="text-xs text-brand-700 hover:underline">
                {t("Заявка")}
              </Link>
              {l.is_available && (
                <>
                  <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => copy(abs(l.url))}>
                    {t("Копировать")}
                  </button>
                  <ConfirmButton className="btn-ghost px-2 py-1 text-xs text-red-700" question={t("Отключить ссылку? По ней больше нельзя будет зарегистрироваться.")} onConfirm={() => disable(l)}>
                    {t("Отключить")}
                  </ConfirmButton>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
