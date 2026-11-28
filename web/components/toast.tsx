"use client";

import { createContext, useCallback, useContext, useState } from "react";

type Toast = { id: number; msg: string; kind: "success" | "error" | "info" };

const ToastContext = createContext<{
  push: (msg: string, kind?: Toast["kind"]) => void;
} | null>(null);

let seq = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = (msg: string, kind: Toast["kind"] = "success") => {
    const id = ++seq;
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  };

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg ${
              t.kind === "success"
                ? "bg-green-600"
                : t.kind === "error"
                  ? "bg-red-600"
                  : "bg-slate-700"
            }`}
          >
            {t.msg}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
