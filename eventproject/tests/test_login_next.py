"""P2-9 — user_login должен честно и БЕЗОПАСНО обрабатывать ?next= (возврат в SPA).

До фикса вход всегда кидал на legacy `/application/` (или `/avmac/`), игнорируя next →
после Django-логина оператор не возвращался на исходную SPA-страницу. Безопасность:
open-redirect недопустим — внешний/чужой host отбрасывается (safe-redirect).
"""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase


class LoginNextRedirectTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="op_next", password="StrongPass123!"
        )
        self.client = Client()

    def _login(self, **extra):
        return self.client.post(
            "/user_login/",
            {"username": "op_next", "password": "StrongPass123!", **extra},
            REMOTE_ADDR="127.0.0.1",
        )

    def test_redirects_to_safe_relative_next(self):
        resp = self._login(next="/show/5/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/show/5/")

    def test_rejects_offsite_next(self):
        # open-redirect защита: внешний host игнорируется → дефолтный редирект.
        resp = self._login(next="https://evil.example.com/phish")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(resp.url, ("/application/", "/avmac/"))

    def test_rejects_protocol_relative_next(self):
        resp = self._login(next="//evil.example.com/phish")
        self.assertEqual(resp.status_code, 302)
        self.assertIn(resp.url, ("/application/", "/avmac/"))

    def test_default_redirect_without_next(self):
        resp = self._login()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/application/")
