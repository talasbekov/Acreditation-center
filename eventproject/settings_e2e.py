"""Профиль для e2e-тестов (Playwright): живой runserver + файловый SQLite.

Запуск:
    python manage.py migrate --settings=eventproject.settings_e2e
    python manage.py runserver 8088 --settings=eventproject.settings_e2e
"""
from .settings_test import *  # noqa: F401,F403 — берёт base + переопределения test-профиля

# Файловая SQLite вместо :memory:, чтобы данные жили между процессами (seed → runserver)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "e2e.sqlite3",
    }
}

# Rate-limit мешает прогонам форм в цикле
RATELIMIT_ENABLE = False
AXES_ENABLED = False

# Раздача статики dev-сервером
DEBUG = True

# Фиксированный ключ: seed-процесс и runserver должны читать одни и те же шифрованные поля
FERNET_KEYS = ["ZCGrE8a6MqaLn8j1Gy7GxZIzVmoqmmsBQydYI6LEyls="]

