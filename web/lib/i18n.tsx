"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { EventItem } from "./types";

export type Lang = "ru" | "kz" | "en";

type Dict = Record<string, { ru: string; kz: string; en: string }>;

const DICT: Dict = {
  appName: { ru: "Центр аккредитации", kz: "Аккредитация орталығы", en: "Accreditation Center" },
  events: { ru: "Мероприятия", kz: "Іс-шаралар", en: "Events" },
  operators: { ru: "Операторы", kz: "Операторлар", en: "Operators" },
  audit: { ru: "Журнал аудита", kz: "Аудит журналы", en: "Audit log" },
  participants: { ru: "Участники", kz: "Қатысушылар", en: "Participants" },
  exports: { ru: "Выгрузки", kz: "Жүктемелер", en: "Exports" },
  badges: { ru: "Бейджи", kz: "Бейджтер", en: "Badges" },
  customFields: { ru: "Доп. поля", kz: "Қос. өрістер", en: "Custom fields" },
  regLinks: { ru: "Ссылки регистрации", kz: "Тіркеу сілтемелері", en: "Registration links" },
  apiTokens: { ru: "API-токены", kz: "API-токендер", en: "API tokens" },
  logout: { ru: "Выйти", kz: "Шығу", en: "Log out" },
  login: { ru: "Войти", kz: "Кіру", en: "Sign in" },
  changePassword: { ru: "Сменить пароль", kz: "Құпиясөзді ауыстыру", en: "Change password" },
  add: { ru: "Добавить", kz: "Қосу", en: "Add" },
  create: { ru: "Создать", kz: "Құру", en: "Create" },
  save: { ru: "Сохранить", kz: "Сақтау", en: "Save" },
  cancel: { ru: "Отмена", kz: "Болдырмау", en: "Cancel" },
  delete: { ru: "Удалить", kz: "Жою", en: "Delete" },
  edit: { ru: "Редактировать", kz: "Өңдеу", en: "Edit" },
  search: { ru: "Поиск", kz: "Іздеу", en: "Search" },
  city: { ru: "Город", kz: "Қала", en: "City" },
  dates: { ru: "Даты", kz: "Күндер", en: "Dates" },
  code: { ru: "Код", kz: "Коды", en: "Code" },
  accessYes: { ru: "Доступ разрешён", kz: "Рұқсат берілді", en: "Access granted" },
  accessNo: { ru: "Доступ запрещён", kz: "Рұқсат жоқ", en: "Access denied" },
  accessNone: { ru: "Не определён", kz: "Анықталмаған", en: "Undetermined" },
  exported: { ru: "Выгружен", kz: "Жүктелген", en: "Exported" },
  notExported: { ru: "Не выгружен", kz: "Жүктелмеген", en: "Not exported" },
  selfRegistration: { ru: "Саморегистрация", kz: "Өзін-өзі тіркеу", en: "Self-registration" },
};

const LangContext = createContext<{
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: keyof typeof DICT) => string;
  eventName: (e: EventItem) => string;
} | null>(null);

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("ru");

  useEffect(() => {
    const saved = (localStorage.getItem("acc_lang") as Lang) || "ru";
    setLangState(saved);
  }, []);

  const setLang = (l: Lang) => {
    setLangState(l);
    localStorage.setItem("acc_lang", l);
  };

  const t = (key: keyof typeof DICT) => DICT[key]?.[lang] ?? String(key);
  const eventName = (e: EventItem) =>
    lang === "kz" ? e.name_kz : lang === "en" ? e.name_en : e.name_ru;

  return (
    <LangContext.Provider value={{ lang, setLang, t, eventName }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used within LangProvider");
  return ctx;
}
