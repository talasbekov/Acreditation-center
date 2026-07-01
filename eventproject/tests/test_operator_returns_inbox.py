"""Story fe-3.7 — инбокс возвратов оператора (backend-дельты).

Покрытие AC:
  • AC-1a — `?returned=true` фильтр: только `status=submitted AND return_count>0`
    (НЕ `?status=submitted` — тот over-select'ит невозвращённые submitted).
  • AC-1b — `AttendeeListSerializer` несёт `last_return_reason` + `return_count`; masked-safe (ИИН маскирован).
  • AC-1 scope — sub-event (реюз get_operator_attendee_queryset, Q1): cross-tenant не течёт.
  • RBAC — IsOperator (аноним 401/403).

«Возвращена» = submitted + return_count>0 (нет отдельного FSM-статуса, реш.#1).
"""

import json
import re

from django.test import TestCase
from rest_framework.test import APIClient

from eventproject.models import Event
from eventproject.tests.test_attendee_api import (
    VALID_IIN,
    _make_attendee,
    _make_operator,
    _make_request,
)


class OperatorReturnsInboxTests(TestCase):
    def setUp(self):
        self.event1 = Event.objects.create(name_rus="Событие 1", title="E1")
        self.event2 = Event.objects.create(name_rus="Событие 2", title="E2")
        self.op1_user, self.op1 = _make_operator("op1", "operator", event=self.event1)
        self.op2_user, self.op2 = _make_operator("op2", "operator", event=self.event2)
        self.req1 = _make_request(self.event1, self.op1)
        self.req2 = _make_request(self.event2, self.op2)

        # Возвращённая (submitted + return_count>0 + причина).
        self.returned = _make_attendee(self.req1, surname="Возвращён", status="submitted", iin=VALID_IIN)
        self.returned.return_count = 2
        self.returned.last_return_reason = "Нет фото"
        self.returned.save(update_fields=["return_count", "last_return_reason"])
        # Обычный submitted (никогда не возвращался) — НЕ должен попасть в инбокс.
        self.plain_submitted = _make_attendee(self.req1, surname="Отправлен", status="submitted", iin=VALID_IIN)
        # Черновик — не submitted.
        self.draft = _make_attendee(self.req1, surname="Черновик", status="draft", iin=VALID_IIN)
        # Cross-tenant возвращённая под event2 (op1 не должен видеть).
        self.other = _make_attendee(self.req2, surname="Чужой", status="submitted", iin=VALID_IIN)
        self.other.return_count = 1
        self.other.last_return_reason = "Чужая причина"
        self.other.save(update_fields=["return_count", "last_return_reason"])

        self.client = APIClient()
        self.client.force_authenticate(self.op1_user)

    def _rows(self, resp):
        data = resp.data
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def _ids(self, resp):
        return {r["id"] for r in self._rows(resp)}

    def test_returned_filter_only_returned(self):
        resp = self.client.get("/api/v1/attendees/?returned=true")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._ids(resp), {self.returned.id})  # не plain_submitted/draft/other

    def test_status_submitted_overselects_never_returned(self):
        # Доказывает необходимость returned-флага: ?status=submitted тянет невозвращённые.
        resp = self.client.get("/api/v1/attendees/?status=submitted")
        ids = self._ids(resp)
        self.assertIn(self.returned.id, ids)
        self.assertIn(self.plain_submitted.id, ids)  # over-select (не возврат, но submitted)

    def test_dto_carries_return_fields_masked(self):
        resp = self.client.get("/api/v1/attendees/?returned=true")
        row = self._rows(resp)[0]
        self.assertEqual(row["return_count"], 2)
        self.assertEqual(row["last_return_reason"], "Нет фото")
        self.assertIn("iin_masked", row)
        # masked-инвариант: сырого 12-значного ИИН нет нигде в ответе.
        blob = json.dumps(resp.data, ensure_ascii=False, default=str)
        self.assertEqual(re.findall(r"\b\d{12}\b", blob), [])

    def test_cross_tenant_scope_excludes_other_event(self):
        resp = self.client.get("/api/v1/attendees/?returned=true")
        self.assertNotIn(self.other.id, self._ids(resp))  # sub-event scope: чужое событие не течёт

    def test_returned_false_or_absent_no_filter(self):
        # returned!=true → фильтр не применяется (обычный список), возвращённая среди прочих.
        resp = self.client.get("/api/v1/attendees/?returned=false")
        self.assertEqual(resp.status_code, 200)
        ids = self._ids(resp)
        self.assertIn(self.plain_submitted.id, ids)
        self.assertIn(self.draft.id, ids)

    def test_anonymous_denied(self):
        resp = APIClient().get("/api/v1/attendees/?returned=true")
        self.assertIn(resp.status_code, (401, 403))
