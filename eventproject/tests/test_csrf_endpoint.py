"""P2-8 — bootstrap CSRF-cookie для SPA.

GET к JSON DRF-эндпоинту не ставит `csrftoken` cookie, поэтому первый POST из SPA мог
уйти без `X-CSRFToken` → 403. `/api/v1/csrf/` (с `@ensure_csrf_cookie`) гарантированно
ставит cookie до первой мутации.
"""

from django.test import Client, TestCase


class CsrfCookieEndpointTests(TestCase):
    def test_sets_csrftoken_cookie(self):
        resp = Client().get("/api/v1/csrf/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("csrftoken", resp.cookies)
        self.assertTrue(resp.cookies["csrftoken"].value)

    def test_no_auth_required(self):
        # Эндпоинт-сеттер cookie доступен без сессии (его зовут до логина при необходимости).
        resp = Client().get("/api/v1/csrf/")
        self.assertEqual(resp.status_code, 200)
