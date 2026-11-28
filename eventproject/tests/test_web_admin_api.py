"""API страниц администратора для Next.js: те же правила, что у /avmac/, /show_event/, /show_operator/."""

import os
import tempfile
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from eventproject.models import Event, Operator, Request

MEDIA = tempfile.mkdtemp()


def _event(code, days=10):
    today = date.today()
    return Event.objects.create(
        name_rus=f"Событие {code}", name_kaz="Іс-шара", name_eng="Event", event_code=code,
        date_start=today + timedelta(days=days), date_end=today + timedelta(days=days + 2),
    )


@override_settings(MEDIA_ROOT=MEDIA)
class AdminApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("su", "su@example.com", "Strong-pass-123")
        self.op_user = User.objects.create_user("op", password="Strong-pass-123", first_name="Ержан", last_name="Оп")
        self.operator = Operator.objects.create(user=self.op_user, patronymic="П", workplace="ТОО", phone_number="+7")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_only_superuser(self):
        other = APIClient()
        other.force_authenticate(self.op_user)
        self.assertEqual(other.get("/api/v1/admin/home/").status_code, 403)

    def test_home_lists_events_for_900_days(self):
        near, far = _event("NEAR"), _event("FAR", days=1000)
        data = self.client.get("/api/v1/admin/home/").json()
        ids = [e["id"] for e in data["events"]]
        self.assertIn(near.id, ids)
        self.assertNotIn(far.id, ids)
        self.assertEqual(data["operators"][0]["username"], "op")

    def test_create_event_rules(self):
        today = date.today()
        base = {"name_rus": "Форум", "name_kaz": "Форум", "name_eng": "Forum", "event_code": "F1", "city": "1110106945"}
        bad_order = dict(base, date_start=str(today + timedelta(days=5)), date_end=str(today + timedelta(days=1)))
        self.assertIn("раньше даты создания", self.client.post("/api/v1/admin/events/", bad_order, format="json").json()["detail"])
        past = dict(base, date_start=str(today - timedelta(days=5)), date_end=str(today - timedelta(days=1)))
        self.assertIn("Истек", self.client.post("/api/v1/admin/events/", past, format="json").json()["detail"])
        no_name = dict(base, name_rus="", date_start=str(today), date_end=str(today))
        self.assertIn("Название", self.client.post("/api/v1/admin/events/", no_name, format="json").json()["detail"])
        ok = self.client.post("/api/v1/admin/events/", dict(base, date_start=str(today), date_end=str(today)), format="json")
        self.assertEqual(ok.status_code, 201, ok.content)
        event = Event.objects.get(pk=ok.json()["event"]["id"])
        self.assertEqual((event.title, event.city_code, event.start_date), ("Форум", "1110106945", today))

    def test_event_card_and_binding(self):
        ev = _event("CARD")
        Request.objects.create(name="1", event=ev, status="Sent", created_by=self.operator, registration_time=timezone.now())
        Request.objects.create(name="2", event=ev, status="Active", created_by=self.operator, registration_time=timezone.now())
        card = self.client.get(f"/api/v1/admin/events/{ev.id}/").json()
        self.assertEqual(card["unexported"], 1)
        self.assertEqual([o["id"] for o in card["other_operators"]], [self.operator.id])
        self.assertEqual(len(card["active_requests"]), 1)
        bound = self.client.post(f"/api/v1/admin/events/{ev.id}/operators/", {"operator_ids": [self.operator.id]}, format="json")
        self.assertEqual(bound.status_code, 200)
        self.assertTrue(self.operator.events.filter(pk=ev.pk).exists())
        self.assertEqual(self.client.delete(f"/api/v1/admin/events/{ev.id}/operators/{self.operator.id}/").status_code, 200)
        self.assertFalse(self.operator.events.filter(pk=ev.pk).exists())

    def test_delete_event_removes_media(self):
        ev = _event("DEL")
        folder = os.path.join(MEDIA, f"event_{ev.id}")
        os.makedirs(folder)
        open(os.path.join(folder, "x.jpg"), "wb").close()
        resp = self.client.delete(f"/api/v1/admin/events/{ev.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(os.path.exists(folder))
        self.assertFalse(Event.objects.filter(pk=ev.pk).exists())

    @mock.patch("eventproject.views.admin_api.send_operator_link", return_value=True)
    def test_create_operator_sends_link(self, send):
        ev = _event("OP")
        payload = {
            "last_name": "Иванов", "first_name": "Иван", "patronymic": "И", "login": "ivanov", "email": "i@example.com",
            "workplace": "ТОО", "phone_number": "+7700", "event": ev.id,
        }
        resp = self.client.post("/api/v1/admin/operators/", payload, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.json()["email_sent"])
        op = Operator.objects.get(user__username="ivanov")
        self.assertFalse(op.user.has_usable_password())
        self.assertTrue(op.events.filter(pk=ev.pk).exists())
        dup = self.client.post("/api/v1/admin/operators/", payload, format="json")
        self.assertEqual(dup.status_code, 400)
        send.assert_called_once()

    def test_operator_card_and_delete(self):
        card = self.client.get(f"/api/v1/admin/operators/{self.operator.id}/").json()
        self.assertEqual(card["operator"]["username"], "op")
        self.assertEqual(self.client.delete(f"/api/v1/admin/operators/{self.operator.id}/").status_code, 200)
        self.assertFalse(User.objects.filter(username="op").exists())
