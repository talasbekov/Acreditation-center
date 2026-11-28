"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "./api";
import type { Role, Session, SubjectType } from "./types";

interface AuthState {
  session: Session | null;
  ready: boolean;
  isAdmin: boolean;
  login: (login: string, password: string) => Promise<Session>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const STORE_KEY = "acc_session";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (raw) setSession(JSON.parse(raw));
    } catch {
      /* ignore */
    }
    setReady(true);
  }, []);

  const login = useCallback(async (login: string, password: string) => {
    const res = await api<{
      token: string;
      role: Role;
      typ: SubjectType;
      user: Session["user"];
    }>("/auth/login", { method: "POST", auth: false, body: { login, password } });
    const sess: Session = {
      token: res.token,
      role: res.role,
      typ: res.typ,
      user: res.user,
    };
    setToken(sess.token);
    localStorage.setItem(STORE_KEY, JSON.stringify(sess));
    setSession(sess);
    return sess;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    localStorage.removeItem(STORE_KEY);
    setSession(null);
    router.push("/login");
  }, [router]);

  const isAdmin = session?.typ === "user";

  return (
    <AuthContext.Provider
      value={{ session, ready, isAdmin, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
