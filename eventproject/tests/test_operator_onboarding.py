"""Story 2.3 — тесты онбординга операторов (AC-6)."""

import smtplib
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from eventproject.models import Event, Operator
from eventproject.services.operator_onboarding import (
    generate_password,
    generate_username,
)


def _make_operator(username, role, *, force_password_change=False, password="StrongPass123!"):
    user = User.objects.create_user(
        username=username, password=password, email=f"{username}@example.com"
    )
    Operator.objects.create(
        user=user, role=role, force_password_change=force_password_change
    )
    return user


class OperatorOnboardingAPITests(TestCase):
    def setUp(self):
        self.superop = _make_operator("superop", "superoperator")
        self.client = APIClient()
        self.client.force_authenticate(user=self.superop)
        self.event = Event.objects.create(name_rus="Test Event", title="Test Event")

    def _create_payload(self, **overrides):
        payload = {
            "first_name": "Иван",
            "last_name": "Иванов",
            "patronymic": "Иванович",
            "email": "ivan@example.com",
        }
        payload.update(overrides)
        return payload

    def test_create_operator_returns_201_and_generates_username(self):
        resp = self.client.post(
            "/api/v1/operators/",
            self._create_payload(event_ids=[self.event.id]),
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["status"], "created")
        self.assertTrue(data["username"])
        self.assertEqual(data["role"], "operator")
        self.assertEqual(data["email_status"], "sent")
        self.assertTrue(data["force_password_change"])
        self.assertTrue(User.objects.filter(username=data["username"]).exists())
        self.assertIn(self.event.id, data["event_ids"])

    def test_email_sent_with_credentials(self):
        resp = self.client.post(
            "/api/v1/operators/",
            self._create_payload(last_name="Петров", email="petrov@example.com"),
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("petrov@example.com", msg.to)
        self.assertIn(resp.json()["username"], msg.body)
        self.assertIn("Временный пароль:", msg.body)
        self.assertIn("/user_login/", msg.body)

    @patch(
        "eventproject.services.email.send_mail",
        side_effect=smtplib.SMTPException("smtp down"),
    )
    def test_smtp_error_keeps_operator_and_sets_error_status(self, _mock_send):
        resp = self.client.post(
            "/api/v1/operators/",
            self._create_payload(last_name="Сидоров", email="sid@example.com"),
            format="json",
        )
        # AC-3: оператор НЕ откатывается, API возвращает 201 со статусом email_error.
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["status"], "email_error")
        self.assertEqual(data["email_status"], "error")
        operator = Operator.objects.get(id=data["id"])
        self.assertEqual(operator.email_status, "error")
        self.assertTrue(User.objects.filter(id=operator.user_id).exists())

    def test_resend_credentials_generates_new_password(self):
        resp = self.client.post(
            "/api/v1/operators/",
            self._create_payload(last_name="Кузнецов", email="kuz@example.com"),
            format="json",
        )
        op_id = resp.json()["id"]
        operator = Operator.objects.get(id=op_id)
        old_hash = operator.user.password
        mail.outbox.clear()

        with self.assertLogs("eventproject", level="INFO") as cm:
            resp2 = self.client.post(
                f"/api/v1/operators/{op_id}/resend_credentials/", {}, format="json"
            )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["status"], "resent")
        operator.refresh_from_db()
        operator.user.refresh_from_db()
        self.assertNotEqual(operator.user.password, old_hash)
        self.assertEqual(len(mail.outbox), 1)
        # AC-4: статус/timestamp обновлены, audit-лог resend эмитится.
        self.assertEqual(operator.email_status, "sent")
        self.assertIsNotNone(operator.credentials_sent_at)
        self.assertIn(
            "operator.resend_email", [getattr(r, "action", None) for r in cm.records]
        )

    def test_resend_to_operator_without_email_returns_400(self):
        # Создаём оператора напрямую без email; resend не должен ротировать пароль.
        user = User.objects.create_user(username="noemail", password="StrongPass123!", email="")
        operator = Operator.objects.create(user=user, role="operator")
        old_hash = user.password
        resp = self.client.post(
            f"/api/v1/operators/{operator.id}/resend_credentials/", {}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.password, old_hash)  # пароль не тронут

    def test_create_operator_persists_category(self):
        from eventproject.models import Category

        category = Category.objects.create(event=self.event, name="VIP")
        resp = self.client.post(
            "/api/v1/operators/",
            self._create_payload(
                last_name="Категоров",
                email="cat@example.com",
                event_ids=[self.event.id],
                category_id=category.id,
            ),
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["category_id"], category.id)
        operator = Operator.objects.get(id=resp.json()["id"])
        self.assertEqual(operator.category_id, category.id)

    def test_duplicate_email_rejected(self):
        User.objects.create_user(username="existing", password="x", email="dup@example.com")
        resp = self.client.post(
            "/api/v1/operators/",
            self._create_payload(last_name="Дубликатов", email="dup@example.com"),
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_emits_audit_log(self):
        with self.assertLogs("eventproject", level="INFO") as cm:
            self.client.post(
                "/api/v1/operators/",
                self._create_payload(last_name="Логов", email="log@example.com"),
                format="json",
            )
        actions = [getattr(r, "action", None) for r in cm.records]
        self.assertIn("operator.create", actions)

    def test_non_superoperator_cannot_create(self):
        plain = _make_operator("plain", "operator")
        client = APIClient()
        client.force_authenticate(user=plain)
        resp = client.post(
            "/api/v1/operators/",
            self._create_payload(email="a@b.com"),
            format="json",
        )
        self.assertEqual(resp.status_code, 403)


class CredentialGenerationTests(TestCase):
    def test_password_length_and_complexity(self):
        pw = generate_password()
        self.assertGreaterEqual(len(pw), 12)
        self.assertNotEqual(generate_password(), generate_password())

    def test_username_transliterated_and_unique(self):
        u1 = generate_username("Иван", "Иванов")
        self.assertTrue(u1)
        self.assertTrue(all(ord(c) < 128 for c in u1))  # кириллица транслитерирована
        User.objects.create_user(username=u1, password="x")
        u2 = generate_username("Иван", "Иванов")
        self.assertNotEqual(u1, u2)


class ForcePasswordChangeMiddlewareTests(TestCase):
    def _login(self, username, force):
        user = _make_operator(username, "operator", force_password_change=force)
        self.client.force_login(
            user, backend="django.contrib.auth.backends.ModelBackend"
        )
        return user

    def test_flagged_operator_html_is_redirected(self):
        self._login("opflag", force=True)
        resp = self.client.get("/avmac/")  # non-api, non-exempt
        self.assertEqual(resp.status_code, 302)
        self.assertIn("change_password", resp.url)

    def test_flagged_operator_api_gets_403_json(self):
        self._login("opflagapi", force=True)
        resp = self.client.get("/api/v1/operators/")
        # API не может следовать HTML-редиректу → структурный 403.
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("code"), "password_change_required")

    def test_substring_path_does_not_bypass_force(self):
        # Путь с "change_password" как частью сегмента НЕ должен обходить форс.
        self._login("opbypass", force=True)
        resp = self.client.get("/events/change_password_report/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("change_password", resp.url)

    def test_unflagged_operator_not_redirected(self):
        self._login("opnoflag", force=False)
        resp = self.client.get("/api/v1/operators/")
        # Прошёл middleware; DRF блокирует не-супероператора 403 (не форс-403).
        self.assertEqual(resp.status_code, 403)
        self.assertNotEqual(resp.json().get("code"), "password_change_required")
