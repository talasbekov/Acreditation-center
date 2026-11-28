"""API кабинета оператора для Next.js: то же поведение, что у HTML-страниц заявки."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from eventproject.models import Attendee, Event, Operator, Request


def _event(code, days=10):
    today = date.today()
    return Event.objects.create(
        name_rus=f"Событие {code}", name_kaz="Іс-шара", name_eng="Event", event_code=code,
        date_start=today + timedelta(days=days), date_end=today + timedelta(days=days + 2), city_code="1110106945",
    )


def _operator(username, *events, role="operator"):
    user = User.objects.create_user(username=username, password="Strong-pass-123")
    op = Operator.objects.create(user=user, role=role, patronymic="Т", workplace="ТОО")
    op.events.add(*events)
    return user, op


def _attendee(req, **kw):
    data = dict(
        surname="Иванов", firstname="Иван", birthDate=date(1990, 1, 1), post="Инженер", countryId="1000000224",
        docTypeId="1000000002", docNumber=f"N{Attendee.objects.count() + 1}", docBegin=date(2020, 1, 1),
        docEnd=date(2030, 1, 1), sexId="1000000001", visitObjects="Зал", transcription="IVANOV IVAN",
        request=req, dateAdd=timezone.now(), status="draft",
    )
    data.update(kw)
    return Attendee.objects.create(**data)


class CabinetAndRequestTests(TestCase):
    def setUp(self):
        self.event = _event("E1")
        self.far = _event("FAR", days=700)
        self.foreign = _event("E2")
        self.user, self.op = _operator("op1", self.event, self.far)
        self.other_user, self.other = _operator("op2", self.event)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_cabinet_lists_upcoming_events_and_own_requests(self):
        mine = Request.objects.create(
            name="1", event=self.event, status="Active", created_by=self.op, registration_time=timezone.now()
        )
        Request.objects.create(
            name="2", event=self.event, status="Active", created_by=self.other, registration_time=timezone.now()
        )
        data = self.client.get("/api/v1/cabinet/").json()
        self.assertEqual([e["id"] for e in data["events"]], [self.event.id])  # 700 дней — за горизонтом 600
        self.assertEqual([r["id"] for r in data["requests"]], [mine.id])

    def test_create_request_in_own_event_only(self):
        resp = self.client.post("/api/v1/requests/", {"event": self.event.id}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        req = Request.objects.get(pk=resp.json()["id"])
        self.assertEqual((req.status, req.created_by_id), ("Active", self.op.id))
        self.assertEqual(len(req.name), 14)  # ДДММГГГГЧЧММСС, как в старой АЦ
        self.assertEqual(self.client.post("/api/v1/requests/", {"event": self.foreign.id}, format="json").status_code, 404)

    def test_other_operator_request_is_hidden(self):
        theirs = Request.objects.create(
            name="x", event=self.event, status="Active", created_by=self.other, registration_time=timezone.now()
        )
        self.assertEqual(self.client.get(f"/api/v1/requests/{theirs.id}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/requests/{theirs.id}/").status_code, 404)

    def test_send_all_or_nothing(self):
        req = Request.objects.create(
            name="r", event=self.event, status="Active", created_by=self.op, registration_time=timezone.now()
        )
        empty = self.client.post(f"/api/v1/requests/{req.id}/send/")
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.json()["type"], "request_empty")
        a = _attendee(req)
        resp = self.client.post(f"/api/v1/requests/{req.id}/send/")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["problems"][0]["attendee_id"], a.id)
        self.assertEqual(set(resp.json()["problems"][0]["codes"]), {"photo", "doc_scan"})
        Attendee.objects.filter(pk=a.pk).update(photo="p.jpg", docScan="d.jpg")
        ok = self.client.post(f"/api/v1/requests/{req.id}/send/")
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.json()["status"], "Sent")
        self.assertFalse(ok.json()["can_add"])
        a.refresh_from_db()
        self.assertEqual(a.status, "submitted")

    def test_back_to_change_reopens_only_legacy_preview(self):
        req = Request.objects.create(
            name="r", event=self.event, status="Checking", created_by=self.op, registration_time=timezone.now()
        )
        self.assertEqual(self.client.post(f"/api/v1/requests/{req.id}/back-to-change/").json()["status"], "Active")
        req.status = "Sent"
        req.save()
        self.assertEqual(self.client.post(f"/api/v1/requests/{req.id}/back-to-change/").json()["status"], "Sent")

    def test_add_to_sent_request_is_refused(self):
        req = Request.objects.create(
            name="r", event=self.event, status="Sent", created_by=self.op, registration_time=timezone.now()
        )
        resp = self.client.post(
            "/api/v1/attendees/",
            {
                "surname": "Ким", "firstname": "Ли", "birthDate": "1990-01-01", "post": "x", "countryId": "",
                "docTypeId": "1000000002", "docNumber": "Z1", "docBegin": "2020-01-01", "docEnd": "2030-01-01",
                "sexId": "1000000001", "visitObjects": "x", "transcription": "KIM LI", "request": req.id,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(resp.json()["type"], "request_closed")

    def test_deleting_last_attendee_deletes_request(self):
        req = Request.objects.create(
            name="r", event=self.event, status="Active", created_by=self.op, registration_time=timezone.now()
        )
        a1, a2 = _attendee(req), _attendee(req)
        self.assertEqual(self.client.delete(f"/api/v1/attendees/{a1.id}/").status_code, 204)
        self.assertTrue(Request.objects.filter(pk=req.pk).exists())
        self.assertEqual(self.client.delete(f"/api/v1/attendees/{a2.id}/").status_code, 204)
        self.assertFalse(Request.objects.filter(pk=req.pk).exists())

    def test_delete_request(self):
        req = Request.objects.create(
            name="r", event=self.event, status="Active", created_by=self.op, registration_time=timezone.now()
        )
        _attendee(req)
        self.assertEqual(self.client.delete(f"/api/v1/requests/{req.id}/").status_code, 204)
        self.assertFalse(Request.objects.filter(pk=req.pk).exists())


@override_settings(ATTENDEE_API_RATE="2/h", RATELIMIT_ENABLE=True)
class AttendeeRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        event = _event("RL")
        user, op = _operator("op", event)
        self.req = Request.objects.create(
            name="r", event=event, status="Active", created_by=op, registration_time=timezone.now()
        )
        self.client = APIClient()
        self.client.force_authenticate(user)

    def tearDown(self):
        cache.clear()

    def test_third_write_in_an_hour_is_refused(self):
        codes = [
            self.client.post("/api/v1/attendees/", {"request": self.req.id}, format="json").status_code
            for _ in range(3)
        ]
        self.assertEqual(codes[:2], [400, 400])
        self.assertEqual(codes[2], 429)
