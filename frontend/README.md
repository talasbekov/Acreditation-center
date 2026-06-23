# Frontend — кабинет оператора (React SPA)

React-фронтенд системы аккредитации (Increment 2). Подключается к Django/DRF backend `/api/v1/`.

**Стек:** React 19 + Vite 8 (TypeScript) · TailwindCSS v4 + shadcn/ui · TanStack Query v5 · React Router v7 · React Hook Form + zod · Vitest.

## Установка и запуск

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (dev-сервер с прокси на Django :8000)
npm run build      # production-сборка → dist/
npm run test       # Vitest (unit-тесты)
npm run lint       # oxlint
```

Backend должен быть запущен на `http://localhost:8000` (Vite проксирует `/api`, `/user_login`, `/logout`).

## ⚠️ Session / CSRF в локальной разработке

Backend по умолчанию использует **secure-cookies + SSL-redirect** (`CSRF_COOKIE_SECURE`, `SESSION_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `CSRF_COOKIE_SAMESITE='Strict'`). Чтобы session/CSRF работали по локальному HTTP, в Django `.env` задайте dev-override:

```env
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://localhost:5173
```

`ALLOWED_HOSTS` **обязателен** (без дефолта): Vite-прокси с `changeOrigin:true` шлёт `Host: localhost:8000`. Все пять override'ов нужны вместе — без них secure-cookie не ставятся / запрос 400/403. Vite-прокси делает запросы **same-origin** (через `:5173`), поэтому `SameSite=Strict` cookie работают и CORS не требуется. Для прода (Nginx) фронт раздаётся из `dist/`, `/api/v1/` → Gunicorn (см. `architecture.md`).

## Структура

```
src/
├── api/         # DRF-клиент (client.ts: session+CSRF) и эндпоинты (attendees.ts)
├── components/  # UI-компоненты; ui/ — shadcn/ui примитивы
├── pages/       # страницы-маршруты
├── lib/         # утилиты (cn, csrf, auth)
└── types/       # TypeScript-типы DRF-контрактов
```

## Границы (Strangler Fig)

- React SPA монтируется только в `#react-root`; потребляет только `/api/v1/` (DRF).
- Legacy Django-шаблоны и их CSS **не трогаются** (`/`, `/kz/`, `/en/`, `/qr/`, `/user_login/`).
- Anti-fatigue UX (большие touch-таргеты ≥44px, контраст WCAG AA, шрифт ≥16px) — базовая тема (`src/index.css`), обязательна для всех форм.
