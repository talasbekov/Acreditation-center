"""BE-14 — консистентность structured_context-фильтра на handler'ах логирования."""

from django.conf import settings
from django.test import SimpleTestCase


class LoggingHandlerFilterTests(SimpleTestCase):
    def test_file_handler_has_structured_context_filter(self):
        # BE-14: файловый handler навешивает тот же structured_context-фильтр, что и
        # console_json — атрибуты audit-контекста (user_id/ip/action) присутствуют на
        # записи (консистентность; вывод их В ФАЙЛ дополнительно требует json-форматтера).
        file_handler = settings.LOGGING["handlers"]["file"]
        self.assertIn("structured_context", file_handler.get("filters", []))

    def test_console_json_handler_keeps_filter(self):
        console = settings.LOGGING["handlers"]["console_json"]
        self.assertIn("structured_context", console.get("filters", []))
