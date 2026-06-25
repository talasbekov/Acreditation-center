"""P1-8 — миграция 0021 не должна валиться из-за одной нечитаемой зашифрованной строки.

`normalize_blank_iin` дешифрует `Attendee.iin` построчно. Одна повреждённая строка
(или строка под ротированным `FIELD_ENCRYPTION_KEY`) не должна прерывать всю миграцию
и блокировать деплой — её надо пропустить, продолжив нормализацию остальных.
"""

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

_migration = importlib.import_module("eventproject.migrations.0021_normalize_blank_iin")


class _Unreadable:
    """Строка, чтение `.iin` которой бросает (имитация повреждения/ротации ключа)."""

    id = 2

    @property
    def iin(self):
        raise ValueError("decrypt failed")


class NormalizeBlankIinResilienceTests(SimpleTestCase):
    def _run_with_rows(self, rows):
        fake_model = MagicMock()
        (
            fake_model.objects.filter.return_value.only.return_value.iterator.return_value
        ) = iter(rows)
        fake_apps = MagicMock()
        fake_apps.get_model.return_value = fake_model
        _migration.normalize_blank_iin(fake_apps, None)
        return fake_model

    def test_skips_unreadable_row_and_normalizes_blank(self):
        rows = [
            SimpleNamespace(id=1, iin=""),            # пустой → должен стать NULL
            _Unreadable(),                            # нечитаемый → пропуск, без падения
            SimpleNamespace(id=3, iin="900101300007"),  # валидный → не трогаем
        ]
        fake_model = self._run_with_rows(rows)
        # Не бросило исключение; обновление вызвано один раз (для собранных пустых id).
        fake_model.objects.filter.return_value.update.assert_called_once_with(iin=None)

    def test_no_update_when_no_blanks(self):
        rows = [_Unreadable(), SimpleNamespace(id=3, iin="900101300007")]
        fake_model = self._run_with_rows(rows)
        fake_model.objects.filter.return_value.update.assert_not_called()
