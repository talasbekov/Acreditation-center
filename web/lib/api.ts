/**
 * Клиент Django API (`/api/v1/`). Тот же origin, что и интерфейс: в разработке
 * Next.js проксирует `/api/` на Django (next.config.mjs), в бою — nginx.
 *
 * Авторизация — Django-сессия (cookie `sessionid`). На мутирующих запросах
 * отправляем `X-CSRFToken` из cookie `csrftoken`.
 */

export const API_PREFIX = "/api/v1";

/** Ошибка API в формате RFC 7807 (eventproject/api/exceptions.py). */
export interface Problem {
  type?: string;
  field?: string | null;
  params?: Record<string, unknown>;
  detail?: string | null;
  errors?: Record<string, string>;
  code?: string;
  [key: string]: unknown;
}

export class ApiException extends Error {
  status: number;
  problem: Problem;
  constructor(status: number, problem: Problem) {
    super(problem.detail || problem.type || `HTTP ${status}`);
    this.status = status;
    this.problem = problem;
  }
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export async function ensureCsrf(): Promise<void> {
  if (getCsrfToken()) return;
  await fetch(`${API_PREFIX}/csrf/`, { credentials: "include" });
}

type Query = Record<string, string | number | boolean | undefined | null>;

export function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `${path}${path.includes("?") ? "&" : "?"}${s}` : path;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Query;
}

async function parse(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

async function send(path: string, init: RequestInit): Promise<Response> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (UNSAFE.has(method)) {
    await ensureCsrf();
    const token = getCsrfToken();
    if (token) headers.set("X-CSRFToken", token);
  }
  const res = await fetch(path, { ...init, method, headers, credentials: "include" });
  if (!res.ok) {
    const body = (await parse(res)) as Problem | undefined;
    const problem: Problem = body && typeof body === "object" ? body : {};
    if (!problem.type && problem.code) problem.type = String(problem.code);
    throw new ApiException(res.status, problem);
  }
  return res;
}

/** JSON-запрос к `/api/v1${path}`. */
export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query } = opts;
  const headers: Record<string, string> = { Accept: "application/json" };
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body; // boundary ставит браузер
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await send(withQuery(API_PREFIX + path, query), { method, headers, body: payload });
  if (res.status === 204) return undefined as T;
  return (await parse(res)) as T;
}

/** Бинарный ответ (ZIP, JSON-файл, PDF) для скачивания. */
export async function apiBlob(path: string, query?: Query, method = "GET"): Promise<{ blob: Blob; filename: string | null }> {
  const res = await send(withQuery(API_PREFIX + path, query), { method });
  const cd = res.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return { blob: await res.blob(), filename: m ? decodeURIComponent(m[1]) : null };
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Скачать файл из API и сохранить под именем из ответа (или запасным). */
export async function download(path: string, fallbackName: string, query?: Query, method = "GET") {
  const { blob, filename } = await apiBlob(path, query, method);
  saveBlob(blob, filename || fallbackName);
}

/** Страница DRF: `{count, next, previous, results}`. */
export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** Все страницы списка подряд (списки в АЦ небольшие: сотни записей). */
export async function apiAll<T>(path: string, query?: Query): Promise<T[]> {
  const out: T[] = [];
  let page = 1;
  for (;;) {
    const data = await api<Page<T> | T[]>(path, { query: { ...query, page } });
    if (Array.isArray(data)) return data;
    out.push(...data.results);
    if (!data.next) return out;
    page += 1;
  }
}

/**
 * Путь к файлу Django (`/media/...`) без origin. DRF строит абсолютный URL от
 * адреса, на который пришёл запрос; за прокси это адрес Django, а cookie сессии
 * есть только у адреса интерфейса — поэтому берём только путь.
 */
export function mediaPath(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url, "http://x");
    return u.pathname + u.search;
  } catch {
    return url;
  }
}

/** Скачать файл со старого адреса Django (не `/api/v1`), например `/download_json/5/`. */
export async function downloadLegacy(path: string, fallbackName: string, method: "GET" | "POST" = "GET") {
  const res = await send(path, { method });
  const cd = res.headers.get("Content-Disposition") || "";
  const m = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  saveBlob(await res.blob(), m ? decodeURIComponent(m[1]) : fallbackName);
}

/**
 * POST на старый адрес Django без перехода по редиректу. Успех старых форм —
 * 302/303 на HTML-страницу: здесь это `{ redirected: true }`. Иначе — текст ответа
 * (например «Новых записей нет») и код статуса.
 */
export async function postLegacy(path: string): Promise<{ redirected: boolean; status: number; text: string }> {
  await ensureCsrf();
  const headers = new Headers();
  const token = getCsrfToken();
  if (token) headers.set("X-CSRFToken", token);
  const res = await fetch(path, { method: "POST", headers, credentials: "include", redirect: "manual" });
  if (res.type === "opaqueredirect" || (res.status >= 300 && res.status < 400)) {
    return { redirected: true, status: res.status, text: "" };
  }
  return { redirected: false, status: res.status, text: await res.text() };
}

/** POST JSON → бинарный ответ (например, PNG предпросмотра бейджа). */
export async function apiBlobPost(path: string, body: unknown): Promise<Blob> {
  const res = await send(API_PREFIX + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.blob();
}
