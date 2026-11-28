"""Локальная разработка Next.js-интерфейса: Django на SQLite, без HTTPS.

Запуск: `python manage.py runserver 8000 --settings=eventproject.settings_dev`.
Секреты разработки (SECRET_KEY, FERNET_KEYS) создаются один раз в `.dev/secrets.json`
(каталог в .gitignore), чтобы зашифрованные ИИН читались между перезапусками.
Только для локальной машины, не для серверов.
"""

import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

_DEV_DIR = Path(__file__).resolve().parent.parent / ".dev"
_DEV_DIR.mkdir(exist_ok=True)
_SECRETS = _DEV_DIR / "secrets.json"
if not _SECRETS.exists():
    _SECRETS.write_text(
        json.dumps({"SECRET_KEY": secrets.token_urlsafe(50), "FERNET_KEYS": Fernet.generate_key().decode()}),
        encoding="utf-8",
    )
_values = json.loads(_SECRETS.read_text(encoding="utf-8"))

os.environ.setdefault("SECRET_KEY", _values["SECRET_KEY"])
os.environ.setdefault("FERNET_KEYS", _values["FERNET_KEYS"])
os.environ.setdefault("AVALON_API_KEY", "dev-avalon-key")
os.environ.setdefault("KAZENERGY_API_KEY", "dev-kazenergy-key")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1")
os.environ.setdefault("CSRF_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
for _name in ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"):
    os.environ.setdefault(_name, "unused")
os.environ.setdefault("DB_PORT", "5432")

from .settings import *  # noqa: E402,F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": _DEV_DIR / "dev.sqlite3"}}
MEDIA_ROOT = _DEV_DIR / "media"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0

# Второй этап: фоновые задачи сразу (без воркера); закрытые файлы — в .dev/private.
JOBS_RUN_INLINE = True
PRIVATE_FILES_ROOT = str(_DEV_DIR / "private")
