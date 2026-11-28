"use client";

/** Сообщение об успехе или ошибке над страницей (`success_message` / `error_message`). */
export type NoticeValue = { ok: boolean; text: string } | null;

export default function Notice({ value }: { value: NoticeValue }) {
  if (!value) return null;
  return (
    <div
      role={value.ok ? "status" : "alert"}
      className={`mb-4 rounded-lg px-3 py-2 text-sm ${value.ok ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}
    >
      {value.text}
    </div>
  );
}
