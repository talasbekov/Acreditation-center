"use client";

import { useEffect } from "react";

export function Badge({
  color,
  children,
}: {
  color: "green" | "red" | "gray" | "blue" | "amber";
  children: React.ReactNode;
}) {
  const map = {
    green: "bg-green-100 text-green-800",
    red: "bg-red-100 text-red-800",
    gray: "bg-slate-100 text-slate-700",
    blue: "bg-blue-100 text-blue-800",
    amber: "bg-amber-100 text-amber-800",
  };
  return <span className={`badge ${map[color]}`}>{children}</span>;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 sm:p-8"
      onClick={onClose}
    >
      <div
        className={`card my-8 w-full ${wide ? "max-w-3xl" : "max-w-lg"} p-6`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
          <button onClick={onClose} className="btn-ghost px-2 py-1 text-xl leading-none">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center text-slate-500">
      <div className="mb-2 text-4xl">📭</div>
      <p>{text}</p>
    </div>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600" />
    </div>
  );
}

export function Field({
  label,
  required,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="label">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
