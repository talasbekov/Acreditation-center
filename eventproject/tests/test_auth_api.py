"""API входа для Next.js: те же правила, что у HTML-страницы входа и смены пароля."""

from django.contrib.auth.models import User
from django.test import Client, TestCase

from eventproject.models import Operator, OperatorAccessEvent


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.op_user = User.objects.create_user(
            username="op", password="Old-pass-123", first_name="Иван", last_name="Петров"
        )
        self.operator = Operator.objects.create(
            user=self.op_user, patronymic="И", phone_number="+77001234567", workplace="ТОО", role="operator"
        )

    def _csrf(self):
        self.client.get("/api/v1/csrf/")
        return self.client.cookies["csrftoken"].value

    def _login(self, username="op", password="Old-pass-123"):
        token = self._csrf()
        return self.client.post(
            "/api/v1/auth/login/",
            {"username": username, "password": password},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_login_requires_csrf(self):
        resp = self.client.post(
            "/api/v1/auth/login/", {"username": "op", "password": "Old-pass-123"}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_login_ok_returns_profile_and_records_access(self):
        resp = self._login()
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body["role"], "operator")
        self.assertEqual(body["operator_id"], self.operator.id)
        self.assertTrue(OperatorAccessEvent.objects.filter(operator=self.operator, event_type="login").exists())
        me = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "op")

    def test_wrong_password(self):
        resp = self._login(password="nope")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["type"], "login_bad")

    def test_deactivated_account(self):
        self.op_user.is_active = False
        self.op_user.save()
        resp = self._login()
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["type"], "account_disabled")

    def test_me_requires_login(self):
        self.assertIn(self.client.get("/api/v1/auth/me/").status_code, (401, 403))

    def test_logout(self):
        self._login()
        token = self.client.cookies["csrftoken"].value
        resp = self.client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(resp.status_code, 204)
        self.assertIn(self.client.get("/api/v1/auth/me/").status_code, (401, 403))

    def _change(self, old, new, repeat):
        token = self.client.cookies["csrftoken"].value
        return self.client.post(
            "/api/v1/auth/change-password/",
            {"old_password": old, "new_password": new, "new_password_repeat": repeat},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_change_password_rules(self):
        self._login()
        self.assertEqual(self._change("Old-pass-123", "Brand-new-456", "other").json()["type"], "pw_mismatch")
        self.assertEqual(self._change("bad", "Brand-new-456", "Brand-new-456").json()["type"], "pw_wrong_old")
        self.assertEqual(self._change("Old-pass-123", "123", "123").json()["type"], "pw_weak")
        resp = self._change("Old-pass-123", "Brand-new-456", "Brand-new-456")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.op_user.refresh_from_db()
        self.assertTrue(self.op_user.check_password("Brand-new-456"))
        # сессия жива после смены пароля
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)

    def test_forced_change_blocks_api_but_not_auth(self):
        self.operator.force_password_change = True
        self.operator.save()
        self._login()
        self.assertTrue(self.client.get("/api/v1/auth/me/").json()["force_password_change"])
        blocked = self.client.get("/api/v1/rbac-check/")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["code"], "password_change_required")
        self.assertEqual(self._change("Old-pass-123", "Brand-new-456", "Brand-new-456").status_code, 200)
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.force_password_change)
        self.assertEqual(self.client.get("/api/v1/rbac-check/").status_code, 200)
