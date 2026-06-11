import json
import logging
from unittest.mock import patch

from django.conf import settings
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.module_loading import import_string


class StructuredLoggingSettingsTests(SimpleTestCase):
    def test_json_formatter_is_configured(self):
        formatter = settings.LOGGING["formatters"]["json"]

        self.assertEqual(
            formatter["()"],
            "pythonjsonlogger.jsonlogger.JsonFormatter",
        )
        self.assertEqual(formatter["rename_fields"]["levelname"], "level")
        self.assertEqual(formatter["rename_fields"]["asctime"], "timestamp")

    def test_console_json_handler_is_used_by_application_loggers(self):
        self.assertEqual(
            settings.LOGGING["handlers"]["console_json"]["formatter"],
            "json",
        )
        self.assertIn("console_json", settings.LOGGING["root"]["handlers"])

        for logger_name in (
            "django",
            "celery",
            "celery.task",
            "eventproject",
            "request_logger",
        ):
            self.assertIn(
                "console_json",
                settings.LOGGING["loggers"][logger_name]["handlers"],
            )

    def test_json_formatter_emits_required_fields(self):
        formatter_config = settings.LOGGING["formatters"]["json"]
        formatter_cls = import_string(formatter_config["()"])
        formatter = formatter_cls(
            fmt=formatter_config["fmt"],
            rename_fields=formatter_config["rename_fields"],
            datefmt=formatter_config["datefmt"],
        )

        record = logging.LogRecord(
            name="eventproject",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="test event",
            args=(),
            exc_info=None,
        )
        record.user_id = 42
        record.role = "admin"
        record.action = "health.check"
        record.obj_type = "db"
        record.obj_id = "primary"
        record.ip = "127.0.0.1"

        payload = json.loads(formatter.format(record))

        self.assertEqual(payload["message"], "test event")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["user_id"], 42)
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(payload["action"], "health.check")
        self.assertEqual(payload["obj_type"], "db")
        self.assertEqual(payload["obj_id"], "primary")
        self.assertEqual(payload["ip"], "127.0.0.1")
        self.assertIn("timestamp", payload)


class HealthCheckTests(TestCase):
    def test_health_ok(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "db": "ok"})

    def test_health_url_named(self):
        self.assertEqual(reverse("api_health"), "/api/health/")

    def test_existing_health_still_works(self):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("eventproject.views.health.logger")
    def test_health_when_database_unreachable(self, mocked_logger):
        failing_connection = type(
            "FailingConnection",
            (),
            {
                "ensure_connection": lambda self: (_ for _ in ()).throw(
                    OperationalError()
                )
            },
        )()

        with patch(
            "eventproject.views.health.connections",
            {"default": failing_connection},
        ):
            response = self.client.get(
                "/api/health/",
                REMOTE_ADDR="10.1.2.3",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "error", "db": "unreachable"})
        mocked_logger.critical.assert_called_once_with(
            "DB connectivity check failed",
            extra={
                "user_id": None,
                "role": "system",
                "action": "health.check",
                "obj_type": "db",
                "obj_id": None,
                "ip": "10.1.2.3",
            },
        )
