"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useLang } from "@/lib/i18n";

export function Badge({ color, children }: { color: "green" | "red" | "gray" | "blue" | "amber"; children: React.ReactNode }) {
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
  const { t } = useLang();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 sm:p-8" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`card my-8 w-full ${wide ? "max-w-3xl" : "max-w-lg"} p-6`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          <button type="button" onClick={onClose} className="btn-ghost px-2 py-1 text-xl leading-none" aria-label={t("Закрыть")}>
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
    <div className="rounded-xl border border-dashed border-slate-300 bg-white py-12 text-center text-slate-500">
      <p>{text}</p>
    </div>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16" role="status">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600" />
    </div>
  );
}

export function Field({
  label,
  required,
  error,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="label" htmlFor={htmlFor}>
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  back,
  actions,
}: {
  title: string;
  subtitle?: React.ReactNode;
  back?: { href: string; label: string };
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6">
      {back && (
        <Link href={back.href} className="mb-2 inline-block text-sm text-brand-700 hover:underline">
          ← {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          {subtitle && <div className="mt-1 text-sm text-slate-500">{subtitle}</div>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export function ErrorBox({ text }: { text: string }) {
  if (!text) return null;
  return (
    <div role="alert" className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
      {text}
    </div>
  );
}

/** Кнопка с подтверждением (вместо `confirm()` в старых шаблонах). */
export function ConfirmButton({
  onConfirm,
  question,
  className = "btn-danger",
  children,
  disabled,
}: {
  onConfirm: () => Promise<void> | void;
  question: string;
  className?: string;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <button type="button" className={className} onClick={() => setOpen(true)} disabled={disabled}>
        {children}
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title={t("Подтвердите действие")}>
        <p className="mb-6 text-sm text-slate-700">{question}</p>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>
            {t("Нет")}
          </button>
          <button
            type="button"
            className="btn-danger"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirm();
                setOpen(false);
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("Да")}
          </button>
        </div>
      </Modal>
    </>
  );
}

export function formatDate(v: string | null | undefined): string {
  if (!v) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : v;
}

export function formatDateTime(v: string | null | undefined): string {
  if (!v) return "";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
