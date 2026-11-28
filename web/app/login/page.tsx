"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiException } from "@/lib/api";

export default function LoginPage() {
  const { login, session, ready } = useAuth();
  const router = useRouter();
  const [loginValue, setLoginValue] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (ready && session) router.replace("/events");
  }, [ready, session, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(loginValue, password);
      router.replace("/events");
    } catch (err) {
      if (err instanceof ApiException) setError(err.message);
      else setError("Не удалось подключиться к серверу");
    } finally {
      setLoading(false);
    }
  };

  const quickFill = (l: string, p: string) => {
    setLoginValue(l);
    setPassword(p);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-700 to-brand-900 p-4">
      <div className="card w-full max-w-md p-8">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-3xl">
            🛡️
          </div>
          <h1 className="text-xl font-bold text-slate-900">Центр аккредитации</h1>
          <p className="text-sm text-slate-500">Служба государственной охраны РК</p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Логин</label>
            <input
              className="input"
              value={loginValue}
              onChange={(e) => setLoginValue(e.target.value)}
              autoFocus
              required
            />
          </div>
          <div>
            <label className="label">Пароль</label>
            <input
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? "Вход…" : "Войти"}
          </button>
        </form>

        <div className="mt-6 border-t border-slate-100 pt-4">
          <p className="mb-2 text-center text-xs text-slate-400">
            Демо-доступы (mock API):
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => quickFill("admin", "admin")}
              className="btn-secondary flex-1 text-xs"
            >
              Админ
            </button>
            <button
              onClick={() => quickFill("operator", "operator")}
              className="btn-secondary flex-1 text-xs"
            >
              Оператор
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
