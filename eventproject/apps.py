"""AppConfig для eventproject.

Story 5.3: подключает ``signals.py`` (post_delete cleanup медиафайлов) через
``ready()``. ``default_auto_field`` зафиксирован равным глобальному
``DEFAULT_AUTO_FIELD`` (settings.py) — чтобы не сгенерировать лишнюю миграцию.
"""

from django.apps import AppConfig


class EventprojectConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "eventproject"

    def ready(self):
        from eventproject import signals  # noqa: F401  (регистрация receiver'ов)
