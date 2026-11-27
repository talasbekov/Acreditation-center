"""Этап E (п. 4): настройки Django для сквозного сценария на отдельной базе PostgreSQL.

Все значения — из окружения (см. README.md рядом); данные только синтетические.
"""
import os
from pathlib import Path

from eventproject.settings_test import *  # noqa: F401,F403

E2E_DIR = Path(os.environ["E2E_DIR"])
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("E2E_DB_NAME", "e2e"),
        "USER": os.environ["E2E_DB_USER"],
        "PASSWORD": os.environ["E2E_DB_PASSWORD"],
        "HOST": os.environ.get("E2E_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("E2E_DB_PORT", "5432"),
    }
}
FERNET_KEYS = [os.environ["E2E_FERNET_KEY"]]
MEDIA_ROOT = str(E2E_DIR / "media")
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:18811", "http://127.0.0.1:18811", "http://localhost:18812", "http://127.0.0.1:18812"]
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
RATELIMIT_ENABLE = False
