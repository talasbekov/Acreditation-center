"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { homeFor, useAuth } from "@/lib/auth";
import { ApiException } from "@/lib/api";
import { LANGS, useLang } from "@/lib/i18n";

/** Только адрес этого же сайта (как `_safe_next_url` в старой АЦ). */
function safeNext(raw: string | null): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/login")) return null;
  return raw;
}

function LoginForm() {
  const { login, me, ready } = useAuth();
  const { t, err, lang, setLang } = useLang();
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (ready && me) router.replace(me.force_password_change ? "/change-password" : next || homeFor(me));
  }, [ready, me, next, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
    } catch (ex) {
      setError(ex instanceof ApiException ? err(ex.problem) : t("Не удалось подключиться к серверу"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-700 to-brand-900 p-4">
      <div className="card w-full max-w-md p-8">
        <div className="mb-4 flex justify-end">
          <div className="flex overflow-hidden rounded-lg border border-slate-200" role="group" aria-label={t("Язык")}>
            {LANGS.map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLang(l)}
                aria-pressed={lang === l}
                className={`px-2.5 py-1 text-xs font-semibold uppercase ${
                  lang === l ? "bg-brand-600 text-white" : "bg-white text-slate-500"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
        <div className="mb-6 text-center">
          <h1 className="text-xl font-bold text-slate-900">
            {t("Аккредитационный центр Службы государственной охраны Республики Казахстан")}
          </h1>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label" htmlFor="username">
              {t("Логин")}
            </label>
            <input
              id="username"
              className="input"
              placeholder={t("Введите логин")}
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="password">
              {t("Пароль")}
            </label>
            <input
              id="password"
              type="password"
              className="input"
              placeholder={t("Введите пароль")}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && (
            <div role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? t("Вход…") : t("Войти")}
          </button>
        </form>
        <p className="mt-6 text-center text-sm">
          <a className="text-brand-700 underline" href="/static/docs/instructions.pdf" target="_blank" rel="noopener noreferrer">
            {t("Инструкция по заполнению данных для аккредитации")}
          </a>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
