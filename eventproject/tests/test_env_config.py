"""BE-6 / BE-15 — тесты хелперов загрузки настроек (env_config).

Чистая логика вынесена из settings.py, чтобы быть юнит-тестируемой (DI: config
передаётся параметром, settings.py не импортируется).
"""

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from decouple import UndefinedValueError

from eventproject.env_config import parse_bool_flag, require_env


class RequireEnvTests(SimpleTestCase):
    """BE-6: собрать ВСЕ отсутствующие required-секреты в один ImproperlyConfigured."""

    def test_aggregates_all_missing_into_one_error(self):
        def fake_config(name, **kw):
            if name in ("AVALON_API_KEY", "FERNET_KEYS"):
                raise UndefinedValueError(name)
            return "val-" + name

        with self.assertRaises(ImproperlyConfigured) as cm:
            require_env(
                fake_config,
                {"AVALON_API_KEY": {}, "SECRET_KEY": {}, "FERNET_KEYS": {}},
            )
        msg = str(cm.exception)
        # Оба отсутствующих — в одном сообщении; присутствующий SECRET_KEY — нет.
        self.assertIn("AVALON_API_KEY", msg)
        self.assertIn("FERNET_KEYS", msg)
        self.assertNotIn("SECRET_KEY", msg)
        # Значения секретов не утекают в сообщение.
        self.assertNotIn("val-", msg)

    def test_returns_all_values_when_present(self):
        def fake_config(name, **kw):
            return "val-" + name

        out = require_env(fake_config, {"SECRET_KEY": {}, "ALLOWED_HOSTS": {}})
        self.assertEqual(out, {"SECRET_KEY": "val-SECRET_KEY",
                               "ALLOWED_HOSTS": "val-ALLOWED_HOSTS"})

    def test_forwards_cast_kwarg(self):
        seen = {}

        def fake_config(name, **kw):
            seen[name] = kw
            return "a,b"

        require_env(fake_config, {"FERNET_KEYS": {"cast": list}})
        self.assertIn("cast", seen["FERNET_KEYS"])


class ParseBoolFlagTests(SimpleTestCase):
    """BE-15: typo не должен молча отключать секьюрный флаг."""

    def test_recognized_truthy(self):
        self.assertEqual(parse_bool_flag("yes", False), (True, True))
        self.assertEqual(parse_bool_flag(" On ", False), (True, True))

    def test_recognized_falsy(self):
        self.assertEqual(parse_bool_flag("off", True), (False, True))
        self.assertEqual(parse_bool_flag("", True), (False, True))

    def test_unrecognized_falls_back_to_default_true(self):
        # «yess»/«enabled» при default=True → НЕ молча False, а default + recognized=False.
        self.assertEqual(parse_bool_flag("yess", True), (True, False))

    def test_unrecognized_falls_back_to_default_false(self):
        self.assertEqual(parse_bool_flag("enabled", False), (False, False))
