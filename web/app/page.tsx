"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { homeFor, useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";

export default function Home() {
  const { me, ready } = useAuth();
  const { t } = useLang();
  const router = useRouter();

  useEffect(() => {
    if (ready) router.replace(me ? homeFor(me) : "/login");
  }, [ready, me, router]);

  return <div className="flex min-h-screen items-center justify-center text-slate-400">{t("Загрузка…")}</div>;
}
