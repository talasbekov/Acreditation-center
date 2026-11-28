"use client";

import { isAdmin, useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { ErrorBox } from "../ui";

/** Страницы администратора — только суперпользователю (как `user_passes_test(is_superuser)`). */
export default function AdminOnly({ children }: { children: React.ReactNode }) {
  const { me } = useAuth();
  const { t } = useLang();
  if (!isAdmin(me)) return <ErrorBox text={t("Нет доступа к этой странице")} />;
  return <>{children}</>;
}
