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
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копируем только requirements сначала (для кеширования слоев)
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Собираем статику (опционально, может делаться через volume)
RUN python manage.py collectstatic --noinput || true

# Открываем порт
EXPOSE 8000

# Команда по умолчанию (может быть переопределена в docker-compose)
CMD ["gunicorn", "eventproject.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
