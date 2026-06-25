"""FE-1 — RBAC-scoped список Request (`/api/v1/requests/`) для селектора «категории».

`Attendee.request` — FK на Request; форма участника выбирает Request из списка,
scoped по событиям оператора (тот же `get_operator_events`, что и AttendeeViewSet).
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from eventproject.models import Event, Operator, Request


def _make_operator(username, role="operator", event=None):
    user = User.objects.create_user(username=username, password="StrongPass123!")
    op = Operator.objects.create(user=user, role=role, patronymic="Т")
    if event is not None:
        op.events.add(event)
    return user, op


def _make_request(event, operator, name="Batch"):
    return Request.objects.create(
        name=name, event=event, status="Active", created_by=operator,
        registration_time=timezone.now(),
    )


def _rows(resp):
    return resp.data["results"] if "results" in resp.data else resp.data


class RequestListRbacTests(TestCase):
    def setUp(self):
        self.event1 = Event.objects.create(name_rus="Событие 1", title="E1")
        self.event2 = Event.objects.create(name_rus="Событие 2", title="E2")
        self.u1, self.op1 = _make_operator("op1", event=self.event1)
        self.u2, self.op2 = _make_operator("op2", event=self.event2)
        self.req1 = _make_request(self.event1, self.op1, name="Категория А")
        self.req2 = _make_request(self.event2, self.op2, name="Категория Б")
        self.client = APIClient()
        self.client.force_authenticate(self.u1)

    def test_operator_sees_only_own_event_requests(self):
        resp = self.client.get("/api/v1/requests/")
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in _rows(resp)]
        self.assertIn(self.req1.id, ids)
        self.assertNotIn(self.req2.id, ids)

    def test_request_row_shape(self):
        resp = self.client.get("/api/v1/requests/")
        row = next(r for r in _rows(resp) if r["id"] == self.req1.id)
        self.assertEqual(row["name"], "Категория А")
        self.assertEqual(row["event_id"], self.event1.id)
        self.assertIn("event_name", row)

    def test_anonymous_forbidden(self):
        resp = APIClient().get("/api/v1/requests/")
        self.assertIn(resp.status_code, (401, 403))

    def test_read_only_no_create(self):
        # Селектор — только чтение; POST не разрешён.
        resp = self.client.post("/api/v1/requests/", {"name": "X"}, format="json")
        self.assertEqual(resp.status_code, 405)
