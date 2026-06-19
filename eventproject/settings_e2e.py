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

# M6: НЕ коммитим готовый Fernet-ключ. seed-процесс и runserver должны читать
# одни и те же шифрованные поля, но settings_test генерирует случайный ключ на
# каждый процесс — поэтому выводим стабильный e2e-ключ ДЕТЕРМИНИРОВАННО из
# фиксированного тестового SECRET_KEY. Оба процесса получают один ключ, и в
# исходниках нет валидного «боевого» Fernet-ключа.
import base64 as _b64
import hashlib as _hashlib

FERNET_KEYS = [
    _b64.urlsafe_b64encode(_hashlib.sha256(b"e2e-" + SECRET_KEY.encode()).digest()).decode()
]

