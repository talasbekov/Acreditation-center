"""Деструктивные delete-эндпоинты должны быть POST-only (CSRF / destructive GET).

GET по такому URL не должен ничего удалять (require_POST → 405); удаление —
только POST + CSRF-токен (CsrfViewMiddleware/csrf_protect).
"""
import tempfile
from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone

from eventproject.models import Event, Request, Operator


# Изолируем файловую систему: delete_event делает rmtree(MEDIA_ROOT/event_<id>),
# поэтому MEDIA_ROOT указываем на временный каталог, а не на реальный media/.
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DeleteEndpointsPostOnlyTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="su", password="pw12345678", email="su@example.com"
        )
        self.op_user = User.objects.create_user(username="op", password="pw12345678")
        self.operator = Operator.objects.create(
            user=self.op_user, patronymic="T", phone_number="+77001234567",
            workplace="office", role="operator",
        )
        self.event = Event.objects.create(
            name_rus="Событие", name_kaz="Оқиға", name_eng="Event",
            event_code="DEL01", date_start=date.today(),
            date_end=date.today() + timedelta(days=3), city_code="ALA",
        )
        self.req = Request.objects.create(
            name="Заявка", event=self.event, status="Active",
            created_by=self.operator, registration_time=timezone.now(),
        )

    # ---- delete_request (operator-owned) ----
    def test_delete_request_get_rejected(self):
        self.client.force_login(self.op_user)
        resp = self.client.get(f"/delete_request/{self.req.id}/")
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Request.objects.filter(pk=self.req.id).exists())

    def test_delete_request_post_deletes(self):
        self.client.force_login(self.op_user)
        resp = self.client.post(f"/delete_request/{self.req.id}/")
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Request.objects.filter(pk=self.req.id).exists())

    # ---- delete_event (superuser) ----
    def test_delete_event_get_rejected(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(f"/delete_event/{self.event.id}/")
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Event.objects.filter(pk=self.event.id).exists())

    def test_delete_event_post_deletes(self):
        self.client.force_login(self.superuser)
        resp = self.client.post(f"/delete_event/{self.event.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Event.objects.filter(pk=self.event.id).exists())

    # ---- delete_operator (superuser) ----
    def test_delete_operator_get_rejected(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(f"/delete_operator/{self.op_user.username}/")
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Operator.objects.filter(pk=self.operator.id).exists())

    def test_delete_operator_post_deletes(self):
        self.client.force_login(self.superuser)
        resp = self.client.post(f"/delete_operator/{self.op_user.username}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Operator.objects.filter(pk=self.operator.id).exists())

    # ---- en / kz delete_request parity ----
    def test_en_delete_request_get_rejected(self):
        self.client.force_login(self.op_user)
        resp = self.client.get(f"/en/delete_request/{self.req.id}/")
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Request.objects.filter(pk=self.req.id).exists())

    def test_en_delete_request_post_deletes(self):
        self.client.force_login(self.op_user)
        resp = self.client.post(f"/en/delete_request/{self.req.id}/")
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Request.objects.filter(pk=self.req.id).exists())

    def test_kz_delete_request_get_rejected(self):
        self.client.force_login(self.op_user)
        resp = self.client.get(f"/kz/delete_request/{self.req.id}/")
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Request.objects.filter(pk=self.req.id).exists())

    def test_kz_delete_request_post_deletes(self):
        self.client.force_login(self.op_user)
        resp = self.client.post(f"/kz/delete_request/{self.req.id}/")
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Request.objects.filter(pk=self.req.id).exists())
