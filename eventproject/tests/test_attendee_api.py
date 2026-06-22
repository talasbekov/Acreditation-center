"""Story 3.4 — тесты DRF AttendeeViewSet (AC-7)."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from eventproject.models import Attendee, Category, Event, Operator, Request

KZ = "1000000105"
OTHER = "2000000200"
VALID_IIN = "851205301234"  # 1985-12-05, муж (Story 3.1) — у фикстур attendee
BDATE = date(1985, 12, 5)
CREATE_IIN = "010314600078"  # 2001-03-14, жен — для новых участников (не коллизит)
CREATE_BDATE = "2001-03-14"


def _make_operator(username, role, event=None):
    user = User.objects.create_user(username=username, password="StrongPass123!")
    op = Operator.objects.create(
        user=user, role=role, patronymic="Тест", phone_number="+70000000000",
        workplace="HQ",
    )
    if event is not None:
        op.events.add(event)
    return user, op


def _make_request(event, operator, name="Batch"):
    return Request.objects.create(
        name=name, event=event, status="Active", created_by=operator,
        registration_time=timezone.now(),
    )


def _make_attendee(request, category=None, **over):
    data = dict(
        surname="Существующий", firstname="Тест", post="P", countryId=KZ,
        docTypeId="ID", docSeries="AB", docIssue="МВД", sexId="M",
        visitObjects="Зал", transcription="T", request=request, category=category,
        dateAdd=timezone.now(), birthDate=BDATE, iin=VALID_IIN, status="draft",
    )
    data.update(over)
    return Attendee.objects.create(**data)


class AttendeeApiBase(TestCase):
    def setUp(self):
        self.event1 = Event.objects.create(name_rus="E1", title="Event 1")
        self.event2 = Event.objects.create(name_rus="E2", title="Event 2")
        self.op_user, self.op = _make_operator("op", "operator", event=self.event1)
        self.other_user, self.other_op = _make_operator(
            "other", "operator", event=self.event2
        )
        self.category1 = Category.objects.create(event=self.event1, name="VIP")
        self.request1 = _make_request(self.event1, self.op)
        self.request2 = _make_request(self.event2, self.other_op)
        self.attendee1 = _make_attendee(self.request1, self.category1)
        self.attendee2 = _make_attendee(self.request2, surname="Чужой")
        self.client = APIClient()
        self.client.force_authenticate(self.op_user)

    def _payload(self, **over):
        p = dict(
            surname="Иванов", firstname="Иван", post="Менеджер", countryId=KZ,
            docTypeId="ID", docSeries="AB", docIssue="МВД", sexId="M",
            visitObjects="Зал A", transcription="Ivanov Ivan",
            request=self.request1.id, birthDate=CREATE_BDATE, iin=CREATE_IIN,
        )
        p.update(over)
        return p


class AttendeeCreateTests(AttendeeApiBase):
    def test_create_valid_resident(self):
        resp = self.client.post("/api/v1/attendees/", self._payload(), format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "draft")
        self.assertTrue(resp.data["is_resident"])
        self.assertEqual(resp.data["iin"], CREATE_IIN)

    def test_create_valid_non_resident(self):
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(countryId=OTHER, iin=None, birthDate=None),
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data["is_resident"])
        self.assertIsNone(resp.data["iin"])

    def test_create_invalid_iin_400_and_not_saved(self):
        before = Attendee.objects.count()
        resp = self.client.post(
            "/api/v1/attendees/", self._payload(iin="851205301235"), format="json"
        )  # неверная контрольная цифра
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["field"], "iin")
        self.assertEqual(Attendee.objects.count(), before)

    def test_create_in_foreign_event_forbidden(self):
        resp = self.client.post(
            "/api/v1/attendees/", self._payload(request=self.request2.id), format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_duplicate_iin_rejected(self):
        # attendee1 уже имеет VALID_IIN в event1 → дубль с тем же ИИН отклоняется.
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(iin=VALID_IIN, birthDate="1985-12-05"),
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["field"], "iin")


class AttendeeEditLockTests(AttendeeApiBase):
    def test_edit_locked_when_ready(self):
        self.attendee1.status = "ready"
        self.attendee1.save(update_fields=["status"])
        resp = self.client.patch(
            f"/api/v1/attendees/{self.attendee1.id}/", {"post": "X"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_delete_locked_when_exported(self):
        self.attendee1.status = "exported"
        self.attendee1.save(update_fields=["status"])
        resp = self.client.delete(f"/api/v1/attendees/{self.attendee1.id}/")
        self.assertEqual(resp.status_code, 403)

    def test_edit_allowed_when_draft(self):
        resp = self.client.patch(
            f"/api/v1/attendees/{self.attendee1.id}/", {"post": "Новый"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)


class AttendeeRbacListTests(AttendeeApiBase):
    def test_list_isolation_and_pagination(self):
        resp = self.client.get("/api/v1/attendees/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertIn(self.attendee1.id, ids)
        self.assertNotIn(self.attendee2.id, ids)

    def test_cross_operator_detail_404(self):
        resp = self.client.get(f"/api/v1/attendees/{self.attendee2.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_category(self):
        resp = self.client.get("/api/v1/attendees/", {"category_id": self.category1.id})
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertIn(self.attendee1.id, ids)

    def test_filter_by_status(self):
        resp = self.client.get("/api/v1/attendees/", {"status": "submitted"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)  # attendee1 в draft

    def test_invalid_status_filter_400(self):
        resp = self.client.get("/api/v1/attendees/", {"status": "bogus"})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_category_filter_400(self):
        resp = self.client.get("/api/v1/attendees/", {"category_id": "abc"})
        self.assertEqual(resp.status_code, 400)


class AttendeeSubmitTests(AttendeeApiBase):
    @patch("eventproject.views.attendee_api.audit_log")
    def test_submit_draft_to_submitted(self, mock_audit):
        resp = self.client.post(f"/api/v1/attendees/{self.attendee1.id}/submit/")
        self.assertEqual(resp.status_code, 200)
        self.attendee1.refresh_from_db()
        self.assertEqual(self.attendee1.status, "submitted")
        actions = [c.kwargs.get("action") for c in mock_audit.call_args_list]
        self.assertIn("attendee.status_change", actions)

    def test_submit_invalid_transition_rejected(self):
        self.attendee1.status = "submitted"
        self.attendee1.save(update_fields=["status"])
        resp = self.client.post(f"/api/v1/attendees/{self.attendee1.id}/submit/")
        self.assertEqual(resp.status_code, 400)


class AttendeePermissionTests(AttendeeApiBase):
    def test_anonymous_forbidden(self):
        client = APIClient()
        resp = client.get("/api/v1/attendees/")
        self.assertIn(resp.status_code, (401, 403))
