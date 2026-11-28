"""API проверки и выгрузки для Next.js: то же, что /dashboard/ и /review/ старой АЦ."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from eventproject.models import Attendee, Event, Operator, Request


def _attendee(req, status, n):
    return Attendee.objects.create(
        surname=f"Фам{n}", firstname="Имя", birthDate=date(1990, 1, 1), post="x", countryId="1000000224",
        docTypeId="1000000002", docNumber=f"D{n}", docBegin=date(2020, 1, 1), docEnd=date(2030, 1, 1),
        sexId="1000000001", visitObjects="x", transcription="X", request=req, dateAdd=timezone.now(),
        status=status, photo="p.jpg", docScan="d.jpg",
    )


class StaffApiTests(TestCase):
    def setUp(self):
        cache.clear()
        today = date.today()
        self.event = Event.objects.create(
            name_rus="Форум", event_code="F", date_start=today + timedelta(days=3), date_end=today + timedelta(days=5)
        )
        op_user = User.objects.create_user("op", password="Strong-pass-123")
        self.op = Operator.objects.create(user=op_user, role="operator", patronymic="x")
        self.op.events.add(self.event)
        sup_user = User.objects.create_user("sup", password="Strong-pass-123")
        Operator.objects.create(user=sup_user, role="superoperator", patronymic="x")
        self.req = Request.objects.create(
            name="R1", event=self.event, status="Sent", created_by=self.op, registration_time=timezone.now()
        )
        self.submitted = _attendee(self.req, "submitted", 1)
        self.ready = _attendee(self.req, "ready", 2)
        self.client = APIClient()
        self.client.force_authenticate(sup_user)
        self.operator_client = APIClient()
        self.operator_client.force_authenticate(op_user)

    def tearDown(self):
        cache.clear()

    def test_operator_has_no_access(self):
        self.assertEqual(self.operator_client.get(f"/api/v1/staff/events/{self.event.id}/dashboard/").status_code, 403)
        self.assertEqual(self.operator_client.post(f"/api/v1/staff/attendees/{self.submitted.id}/start/").status_code, 403)

    def test_dashboard_counts(self):
        d = self.client.get(f"/api/v1/staff/events/{self.event.id}/dashboard/").json()
        self.assertEqual((d["total"], d["ready"], d["review"]), (2, 1, 1))
        self.assertEqual([c["name"] for c in d["categories"]], ["R1"])
        self.assertEqual(d["packages"], [])

    def test_review_flow_resets_dashboard_cache(self):
        self.client.get(f"/api/v1/staff/events/{self.event.id}/dashboard/")  # кэш заполнен
        queue = self.client.get(f"/api/v1/staff/events/{self.event.id}/review/").json()
        self.assertEqual([i["id"] for i in queue["items"]], [self.submitted.id])
        start = self.client.post(f"/api/v1/staff/attendees/{self.submitted.id}/start/")
        self.assertEqual(start.status_code, 200, start.content)
        self.assertIn("взят(а) на проверку", start.json()["message"])
        empty_reason = self.client.post(f"/api/v1/staff/attendees/{self.submitted.id}/return/", {"reason": ""}, format="json")
        self.assertEqual(empty_reason.status_code, 400)
        approve = self.client.post(f"/api/v1/staff/attendees/{self.submitted.id}/approve/")
        self.assertEqual(approve.status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/staff/events/{self.event.id}/dashboard/").json()["ready"], 2)

    def test_return_with_reason(self):
        self.client.post(f"/api/v1/staff/attendees/{self.submitted.id}/start/")
        r = self.client.post(f"/api/v1/staff/attendees/{self.submitted.id}/return/", {"reason": "Фото не по требованиям"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.submitted.refresh_from_db()
        self.assertEqual((self.submitted.status, self.submitted.review_comment), ("draft", "Фото не по требованиям"))

    def test_unknown_decision_404(self):
        self.assertEqual(self.client.post(f"/api/v1/staff/attendees/{self.submitted.id}/nope/").status_code, 404)
