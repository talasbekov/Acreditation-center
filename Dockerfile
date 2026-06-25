# syntax=docker/dockerfile:1
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    postgresql-client \
    redis-tools \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копируем requirements.txt в рабочую директорию
COPY requirements.txt /app/

# Устанавливаем Python зависимости
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
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

# Открываем порт
EXPOSE 8000

# L5: healthcheck через health-эндпоинт (вернёт 503, если БД недоступна).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health/ || exit 1

# Команда по умолчанию
CMD ["gunicorn", "eventproject.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]