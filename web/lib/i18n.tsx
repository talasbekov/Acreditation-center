"use client";

/**
 * Языки интерфейса: ru / kz / en.
 *
 * Как в HTML-шаблонах старой АЦ (`{% t "Войти" %}`), ключ перевода — сама русская
 * строка. Переводы берутся из `ui_text.UI` (generated/ui-text.json), затем из
 * словаря строк, которых в старой АЦ не было (texts.ts). Нет перевода — русская
 * строка. Подстановки: `t("Добро пожаловать, {name}", { name })`.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import uiText from "./generated/ui-text.json";
import messages from "./generated/messages.json";
import errors from "./generated/errors.json";
import { EXTRA } from "./texts";
import type { Problem } from "./api";

export type Lang = "ru" | "kz" | "en";
export const LANGS: Lang[] = ["ru", "kz", "en"];

type Tr = { kz?: string; en?: string };
type Tri = { ru: string; kz: string; en: string };

const UI = uiText as Record<string, Tr>;
const MESSAGES = messages as Record<string, Tri>;
const ERRORS = errors as Record<string, Tri>;

function fill(s: string, params?: Record<string, unknown>) {
  if (!params) return s;
  return s.replace(/\{(\w+)\}/g, (m, k) => (k in params ? String(params[k]) : m));
}

/** Перевод вне React (для мест без контекста). */
export function translate(ru: string, lang: Lang, params?: Record<string, unknown>) {
  if (lang === "ru") return fill(ru, params);
  const hit = UI[ru]?.[lang] ?? EXTRA[ru]?.[lang];
  return fill(hit ?? ru, params);
}

/** Текст ошибки API по машинному коду; `[ASSUMPTION]`-заглушки заменяем русским. */
export function problemText(problem: Problem | undefined, lang: Lang): string {
  const fallback = translate("Произошла ошибка. Повторите позже.", lang);
  if (!problem) return fallback;
  const code = problem.type || problem.code;
  const entry = code ? ERRORS[code] || MESSAGES[code] : undefined;
  if (entry) {
    let s = entry[lang];
    if (!s || s.startsWith("[ASSUMPTION]")) s = entry.ru;
    return fill(s, problem.params as Record<string, unknown>);
  }
  if (typeof problem.detail === "string" && problem.detail) return problem.detail;
  return fallback;
}

export interface NamedRu {
  name_rus?: string | null;
  name_kaz?: string | null;
  name_eng?: string | null;
}

interface LangState {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (ru: string, params?: Record<string, unknown>) => string;
  /** Название из записи с полями name_rus / name_kaz / name_eng (мероприятия, справочники). */
  name: (o: NamedRu | null | undefined) => string;
  msg: (key: string, params?: Record<string, unknown>) => string;
  err: (p: Problem | undefined) => string;
}

const LangContext = createContext<LangState | null>(null);
const STORE = "acc_lang";

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("ru");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORE) as Lang | null;
      if (saved && LANGS.includes(saved)) setLangState(saved);
    } catch {
      /* приватный режим — остаёмся на ru */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "kz" ? "kk" : lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORE, l);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<LangState>(
    () => ({
      lang,
      setLang,
      t: (ru, params) => translate(ru, lang, params),
      name: (o) => {
        if (!o) return "";
        const v = lang === "kz" ? o.name_kaz : lang === "en" ? o.name_eng : o.name_rus;
        return v || o.name_rus || o.name_kaz || o.name_eng || "";
      },
      msg: (key, params) => {
        const e = MESSAGES[key];
        return e ? fill(e[lang] || e.ru, params) : key;
      },
      err: (p) => problemText(p, lang),
    }),
    [lang, setLang],
  );

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used within LangProvider");
  return ctx;
}
