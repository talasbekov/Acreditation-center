"""Postgres-настройки для race-тестов (`select_for_update` на SQLite — no-op).

Используются тестами, гейченными `@skipUnless(connection.vendor == "postgresql")`:
`test_decision_concurrency.py` (fe-3.6), `test_export_concurrency.py` (hd-1.2).

Контейнер (порт 5434 — не конфликтует с dev-базами на 5432/5433):
    docker run --rm -d --name pg-hd12 \
        -e POSTGRES_DB=testdb -e POSTGRES_USER=testuser -e POSTGRES_PASSWORD=testpass \
        -p 5434:5432 postgres:15-alpine
Прогон:
    .venv/bin/python manage.py test eventproject --settings=eventproject.settings_test_pg

Файл коммитится (hd-1.2): fe-3.6 создавал его как throwaway и удалял — из-за этого
инфраструктуру пересоздавали заново. Postgres-job в CI — отложен (deferred-work.md).
"""

from .settings_test import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "testdb",
        "USER": "testuser",
        "PASSWORD": "testpass",
        "HOST": "127.0.0.1",
        "PORT": "5434",
        "TEST": {"NAME": "test_hd12"},
    }
}
