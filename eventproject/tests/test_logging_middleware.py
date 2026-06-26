import logging

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from eventproject.middleware.logging_middleware import RequestLoggingMiddleware


class _AnonymousUser:
    """Минимальный заглушечный пользователь для RequestFactory-запросов."""

    is_authenticated = False
    id = None
    role = None


class RequestLoggingLevelTests(SimpleTestCase):
    """BE-13: эскалация уровня логов до WARNING для подозрительной активности (AC-1)."""

    def setUp(self):
        self.factory = RequestFactory()

    def _log_record_for(self, status):
        request = self.factory.get("/whatever/")
        request.user = _AnonymousUser()
        middleware = RequestLoggingMiddleware(
            lambda r: HttpResponse(status=status)
        )

        with self.assertLogs("request_logger", level="INFO") as captured:
            middleware(request)

        self.assertEqual(
            len(captured.records),
            1,
            "ожидалась ровно одна запись лога на запрос",
        )
        return captured.records[0]

    def test_normal_response_logs_info(self):
        record = self._log_record_for(200)

        self.assertEqual(record.levelno, logging.INFO)
        self.assertEqual(record.action, "request.completed")

    def test_redirect_response_logs_info(self):
        record = self._log_record_for(302)

        self.assertEqual(record.levelno, logging.INFO)
        self.assertEqual(record.action, "request.completed")

    def test_unauthorized_logs_warning(self):
        record = self._log_record_for(401)

        self.assertEqual(record.levelno, logging.WARNING)
        self.assertEqual(record.action, "request.suspicious")

    def test_forbidden_logs_warning(self):
        record = self._log_record_for(403)

        self.assertEqual(record.levelno, logging.WARNING)
        self.assertEqual(record.action, "request.suspicious")

    def test_rate_limited_logs_warning(self):
        record = self._log_record_for(429)

        self.assertEqual(record.levelno, logging.WARNING)
        self.assertEqual(record.action, "request.suspicious")

    def test_not_found_stays_info(self):
        """Одиночный 404 — не подозрительная активность (может быть нормой)."""
        record = self._log_record_for(404)

        self.assertEqual(record.levelno, logging.INFO)
        self.assertEqual(record.action, "request.completed")

    def test_warning_record_keeps_audit_fields(self):
        """WARNING-запись сохраняет тот же audit-контекст, что и INFO."""
        record = self._log_record_for(403)

        for field in ("user_id", "role", "action", "obj_type", "ip", "status"):
            self.assertTrue(hasattr(record, field))
        self.assertEqual(record.status, 403)
