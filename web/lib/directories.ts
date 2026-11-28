"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { Directories, DirectoryRow } from "./types";
import { useLang } from "./i18n";

const cache = new Map<string, Promise<Directories>>();

/** Справочники СГО (пол, типы документов, категории, страны) на языке интерфейса. */
export function useDirectories(): Directories | null {
  const { lang } = useLang();
  const [data, setData] = useState<Directories | null>(null);
  useEffect(() => {
    let alive = true;
    let p = cache.get(lang);
    if (!p) {
      p = api<Directories>("/directories/", { query: { lang } });
      cache.set(lang, p);
      p.catch(() => cache.delete(lang));
    }
    p.then((d) => alive && setData(d)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [lang]);
  return data;
}

/** Название по коду (как тег `dir_name` в шаблонах); нет в справочнике — пусто. */
export function dirName(rows: DirectoryRow[] | undefined, code: string | null | undefined): string {
  if (!rows || !code) return "";
  return rows.find((r) => r.code === code)?.name ?? "";
}

/** Код страны Казахстана (settings.KZ_COUNTRY_ID): резидентам нужен ИИН, категория скрыта. */
export const KZ_COUNTRY_ID = "1000000105";
