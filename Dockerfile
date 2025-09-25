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

# Переключаемся на пользователя app
USER app

# Открываем порт
EXPOSE 8000

# Команда по умолчанию
CMD ["gunicorn", "eventproject.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]