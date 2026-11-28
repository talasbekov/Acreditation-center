"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import FieldsTab from "@/components/settings/FieldsTab";
import LinksTab from "@/components/settings/LinksTab";
import TokensTab from "@/components/settings/TokensTab";
import { PageHeader } from "@/components/ui";

const TABS = [
  { key: "fields", label: "Доп. поля" },
  { key: "links", label: "Ссылки регистрации" },
  { key: "tokens", label: "API-токены" },
];

/** Настройки мероприятия для оператора: доп. поля, саморегистрация, внешние системы. */
function SettingsPage() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const { me } = useAuth();
  const { t } = useLang();
  const tab = TABS.some((x) => x.key === search.get("tab")) ? (search.get("tab") as string) : "fields";

  return (
    <div>
      <PageHeader
        title={t("Настройки мероприятия")}
        back={{ href: me?.is_superuser ? `/admin/events/${id}` : "/cabinet", label: t("На главную") }}
      />
      <div className="mb-6 flex flex-wrap gap-1 border-b border-slate-200" role="tablist">
        {TABS.map((x) => (
          <button
            key={x.key}
            type="button"
            role="tab"
            aria-selected={tab === x.key}
            onClick={() => router.replace(`/events/${id}/settings?tab=${x.key}`)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              tab === x.key ? "border-brand-600 text-brand-700" : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            {t(x.label)}
          </button>
        ))}
      </div>
      {tab === "fields" && <FieldsTab eventId={id} />}
      {tab === "links" && <LinksTab eventId={id} />}
      {tab === "tokens" && <TokensTab eventId={id} />}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <SettingsPage />
    </Suspense>
  );
}
