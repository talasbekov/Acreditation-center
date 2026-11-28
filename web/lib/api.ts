import type { ApiError } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8080/api/v1";

const TOKEN_KEY = "acc_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiException extends Error {
  status: number;
  body: ApiError;
  constructor(status: number, body: ApiError) {
    super(body.message || body.error || "Ошибка запроса");
    this.status = status;
    this.body = body;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  query?: Record<string, string | number | boolean | undefined>;
}

export async function api<T = unknown>(
  path: string,
  opts: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, auth = true, query } = opts;
  let url = API_BASE + path;
  if (query) {
    const qs = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    });
    const s = qs.toString();
    if (s) url += "?" + s;
  }

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const t = getToken();
    if (t) headers["Authorization"] = "Bearer " + t;
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    throw new ApiException(res.status, (data as ApiError) || { error: "error" });
  }
  return data as T;
}

/**
 * apiForm отправляет multipart/form-data — так спецификация принимает файлы
 * (фон бейджа). Content-Type ставит браузер: вручную его задавать нельзя,
 * иначе потеряется boundary.
 */
export async function apiForm<T = unknown>(
  path: string,
  form: FormData,
  method = "PUT"
): Promise<T> {
  const headers: Record<string, string> = {};
  const t = getToken();
  if (t) headers["Authorization"] = "Bearer " + t;

  const res = await fetch(API_BASE + path, { method, headers, body: form });
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    throw new ApiException(res.status, (data as ApiError) || { error: "error" });
  }
  return data as T;
}

/** apiBlob тянет бинарный ответ (PDF, картинку) с заголовком авторизации. */
export async function apiBlob(
  path: string,
  query?: Record<string, string | undefined>
): Promise<Blob> {
  let url = API_BASE + path;
  if (query) {
    const qs = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => v && qs.set(k, v));
    const s = qs.toString();
    if (s) url += "?" + s;
  }
  const headers: Record<string, string> = {};
  const t = getToken();
  if (t) headers["Authorization"] = "Bearer " + t;

  const res = await fetch(url, { headers });
  if (!res.ok) {
    const text = await res.text();
    let body: ApiError = { error: "error" };
    try {
      body = JSON.parse(text) as ApiError;
    } catch {
      /* не JSON — оставляем общую ошибку */
    }
    throw new ApiException(res.status, body);
  }
  return res.blob();
}

/** downloadBlob сохраняет полученный файл через временную ссылку. */
export function downloadBlob(blob: Blob, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
