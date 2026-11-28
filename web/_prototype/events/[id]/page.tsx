"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { Spinner } from "@/components/ui";
import type { EventItem } from "@/lib/types";
import ParticipantsTab from "@/components/tabs/ParticipantsTab";
import ExportsTab from "@/components/tabs/ExportsTab";
import OperatorsTab from "@/components/tabs/OperatorsTab";
import FieldsTab from "@/components/tabs/FieldsTab";
import LinksTab from "@/components/tabs/LinksTab";
import TokensTab from "@/components/tabs/TokensTab";
import BadgesTab from "@/components/tabs/BadgesTab";

type TabKey =
  | "participants"
  | "exports"
  | "badges"
  | "operators"
  | "fields"
  | "links"
  | "tokens";

export default function EventDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { isAdmin } = useAuth();
  const { t, eventName } = useLang();
  const [event, setEvent] = useState<EventItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("participants");

  const load = useCallback(async () => {
    try {
      const e = await api<EventItem>(`/events/${id}`);
      setEvent(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <Spinner />;
  if (!event)
    return <div className="text-center text-slate-500">Мероприятие не найдено</div>;

  const tabs: { key: TabKey; label: string; show: boolean }[] = [
    { key: "participants", label: t("participants"), show: true },
    { key: "exports", label: t("exports"), show: isAdmin },
    { key: "badges", label: t("badges"), show: isAdmin },
    { key: "operators", label: t("operators"), show: isAdmin },
    { key: "fields", label: t("customFields"), show: !isAdmin },
    { key: "links", label: t("regLinks"), show: !isAdmin },
    { key: "tokens", label: t("apiTokens"), show: true },
  ];
  const visible = tabs.filter((x) => x.show);

  return (
    <div className="mx-auto max-w-6xl">
      <Link href="/events" className="mb-3 inline-block text-sm text-slate-500 hover:text-brand-700">
        ← {t("events")}
      </Link>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900">{eventName(event)}</h1>
            <span className="badge bg-slate-100 font-mono text-slate-600">{event.code}</span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            📍 {event.city} · 🗓 {event.start_date} — {event.end_date} · 👤{" "}
            {event.participant_count}
          </p>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap gap-1 border-b border-slate-200">
        {visible.map((x) => (
          <button
            key={x.key}
            onClick={() => setTab(x.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              tab === x.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {x.label}
          </button>
        ))}
      </div>

      {tab === "participants" && <ParticipantsTab eventId={id} onChanged={load} />}
      {tab === "exports" && <ExportsTab eventId={id} />}
      {tab === "badges" && <BadgesTab eventId={id} />}
      {tab === "operators" && <OperatorsTab eventId={id} />}
      {tab === "fields" && <FieldsTab eventId={id} />}
      {tab === "links" && <LinksTab eventId={id} />}
      {tab === "tokens" && <TokensTab eventId={id} />}
    </div>
  );
}
