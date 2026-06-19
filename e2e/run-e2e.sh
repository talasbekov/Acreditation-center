#!/usr/bin/env bash
# Воспроизводимый прогон E2E-набора (Playwright) на профиле settings_e2e.
# Сбрасывает БД → миграции → seed → runserver:8088 → playwright → teardown.
#
# Использование:
#   e2e/run-e2e.sh                 # весь набор
#   e2e/run-e2e.sh tests/qr*.spec.js   # отдельные файлы (аргументы → playwright)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PY="${PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
export DJANGO_SETTINGS_MODULE=eventproject.settings_e2e

echo "==> Сброс e2e.sqlite3"
rm -f "$PROJECT_ROOT/e2e.sqlite3"

echo "==> Миграции"
"$PY" manage.py migrate --noinput >/dev/null

echo "==> Seed (admin + operator + событие + справочники)"
"$PY" e2e/seed.py

echo "==> Запуск runserver:8088"
"$PY" manage.py runserver 127.0.0.1:8088 --noreload >/tmp/e2e_server.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

echo "==> Ожидание health"
for _ in $(seq 1 30); do
  if curl -sf -m 2 http://127.0.0.1:8088/api/health/ >/dev/null 2>&1; then
    echo "    сервер готов"
    break
  fi
  sleep 1
done

echo "==> Playwright"
cd "$PROJECT_ROOT/e2e"
npx playwright test "$@"
