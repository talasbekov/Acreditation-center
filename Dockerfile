# syntax=docker/dockerfile:1
FROM python:3.12-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# The development Compose waits for PostgreSQL with pg_isready and probes with curl.
ARG INSTALL_DEV_CLIENTS=0
# Этап F: уже выпущенные исправления безопасности дистрибутива ставятся при сборке
# (сканер нашёл исправление для libzstd1, остальные High ждут исправлений Debian).
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends zlib1g poppler-utils \
    && if [ "$INSTALL_DEV_CLIENTS" = "1" ]; then apt-get install -y --no-install-recommends curl postgresql-client; fi \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt в рабочую директорию
COPY requirements.txt /app/

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# Копируются только файлы из разрешённого контекста .dockerignore
COPY . /app/

# Создаем директории
RUN mkdir -p /app/logs /app/media /app/staticfiles

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

# Запускаемся под непривилегированным пользователем (не root).
# Для локальной разработки с bind-mount (./:/app) согласуйте UID хоста
# (build-arg UID=$(id -u)) или используйте именованный том, а не запуск под root.
USER app

# Собираем статику на этапе build → self-contained образ; /app/staticfiles принадлежит
# `app`. Именованный том staticfiles_data (compose) инициализируется отсюда с этими же
# правами, поэтому рантайм-collectstatic больше не упирается в права хоста.
# django.setup() при collectstatic НЕ трогает БД/Redis (ready() лишь регистрирует
# signal-receiver'ы). Dummy-значения нужны только для импорта settings (require_env);
# валидный Fernet-ключ генерируется на лету (EncryptedCharField парсит ключ при загрузке
# моделей). В рантайме все эти значения заменяются из .env/окружения.
RUN FERNET_KEYS="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
    SECRET_KEY=build-only \
    AVALON_API_KEY=build \
    KAZENERGY_API_KEY=build \
    ALLOWED_HOSTS=* \
    DB_NAME=build DB_USER=build DB_PASSWORD=build \
    DJANGO_SETTINGS_MODULE=eventproject.settings \
    python manage.py collectstatic --noinput \
    && rm -f /app/logs/app.log

# Открываем порт
EXPOSE 8000

# L5: healthcheck через health-эндпоинт (вернёт 503, если БД недоступна).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "from http.client import HTTPConnection; c = HTTPConnection('127.0.0.1', 8000, timeout=3); c.request('GET', '/api/health/'); raise SystemExit(c.getresponse().status != 200)"]

# Команда по умолчанию
CMD ["gunicorn", "eventproject.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "gthread", "--threads", "4", "--timeout", "120"]