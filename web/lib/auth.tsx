"use client";

/**
 * Сессия пользователя. Источник правды — Django (`GET /api/v1/auth/me/`);
 * в браузере ничего не храним.
 *
 * Роли как в старой АЦ (`User.role`, eventproject/models.py):
 * superuser — администратор (страницы /avmac/…), superoperator — проверка и
 * выгрузка, operator — заявки и участники, user — без доступа.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, ApiException } from "./api";

export type Role = "superuser" | "superoperator" | "operator" | "user";

export interface Me {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Role;
  is_superuser: boolean;
  operator_id: number | null;
  patronymic: string;
  workplace: string;
  force_password_change: boolean;
}

interface AuthState {
  me: Me | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  refresh: () => Promise<Me | null>;
  setMe: (m: Me | null) => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const m = await api<Me>("/auth/me/");
      setMe(m);
      return m;
    } catch (e) {
      if (e instanceof ApiException && (e.status === 401 || e.status === 403)) {
        setMe(null);
        return null;
      }
      throw e;
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    refresh().catch(() => setReady(true));
  }, [refresh]);

  const login = useCallback(async (username: string, password: string) => {
    const m = await api<Me>("/auth/login/", { method: "POST", body: { username, password } });
    setMe(m);
    return m;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout/", { method: "POST" });
    } finally {
      setMe(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ me, ready, login, logout, refresh, setMe }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** Стартовая страница по роли — как редирект после входа в старой АЦ. */
export function homeFor(me: Me): string {
  if (me.force_password_change) return "/change-password";
  if (me.is_superuser) return "/admin/events";
  return "/cabinet";
}

export const isAdmin = (me: Me | null) => !!me?.is_superuser;
export const isStaff = (me: Me | null) => me?.role === "superuser" || me?.role === "superoperator";
export const isOperatorRole = (me: Me | null) =>
  me?.role === "operator" || me?.role === "superoperator" || me?.role === "superuser";
