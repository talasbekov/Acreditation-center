"""Story fe-3.5 — тесты return-экшена AttendeeViewSet (`POST /attendees/{id}/return/`).

Покрытие AC:
  • AC-1 — FSM in_review→submitted, last_return_reason/return_count, save(update_fields),
    audit через _record_decision (action="attendee.returned", reason), reason-обязателен (400),
    409-guard на не-in_review, masked-safe ответ {id,status} (реш.#6: НЕ AttendeeSerializer).
  • AC-2 — RBAC IsSuperoperator (оператор→403, аноним→401/403), scope/404.

return — на AttendeeViewSet (mirror approve fe-3.4), но: цель SUBMITTED, body-reason (400),
url_path="return" (def return — Python keyword). «Возвращена» = submitted+return_count>0,
НЕ отдельный FSM-статус.
"""

import json
import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from eventproject.models import Event
from eventproject.tests.test_attendee_api import (
    VALID_IIN,
    _make_attendee,
    _make_operator,
    _make_request,
)

REASON = "Фото не соответствует требованиям 3×4"


class AttendeeReturnBase(TestCase):
    def setUp(self):
        self.event1 = Event.objects.create(name_rus="Событие 1", title="E1")
        self.su_user, self.su = _make_operator("su", "superoperator")
        self.op_user, self.op = _make_operator("op", "operator", event=self.event1)
        self.req1 = _make_request(self.event1, self.op)
        self.a_in_review = _make_attendee(
            self.req1, surname="Беков", status="in_review", iin=VALID_IIN
        )
        self.a_draft = _make_attendee(
            self.req1, surname="Драфтов", status="draft", iin=VALID_IIN
        )
        self.a_submitted = _make_attendee(
            self.req1, surname="Сабмитов", status="submitted", iin=VALID_IIN
        )
        self.a_ready = _make_attendee(
            self.req1, surname="Готовый", status="ready", iin=VALID_IIN
        )
        self.a_exported = _make_attendee(
            self.req1, surname="Экспортов", status="exported", iin=VALID_IIN
        )
        self.client = APIClient()
        self.client.force_authenticate(self.su_user)

    def _return(self, attendee_id, reason=REASON, client=None):
        body = {} if reason is None else {"reason": reason}
        return (client or self.client).post(
            f"/api/v1/attendees/{attendee_id}/return/", body, format="json"
        )


class AttendeeReturnHappyPathTests(AttendeeReturnBase):
    def test_return_in_review_to_submitted_200(self):
        resp = self._return(self.a_in_review.id)
        self.assertEqual(resp.status_code, 200)
        self.a_in_review.refresh_from_db()
        self.assertEqual(self.a_in_review.status, "submitted")

    def test_stores_reason_and_increments_count(self):
        # AC-1: причина сохраняется в last_return_reason, return_count += 1.
        self.assertEqual(self.a_in_review.return_count, 0)
        resp = self._return(self.a_in_review.id)
        self.assertEqual(resp.status_code, 200)
        self.a_in_review.refresh_from_db()
        self.assertEqual(self.a_in_review.last_return_reason, REASON)
        self.assertEqual(self.a_in_review.return_count, 1)

    def test_response_is_masked_safe_no_raw_iin(self):
        # реш.#6: ответ = {id, status} (минимально), НЕ AttendeeSerializer (сырой ИИН leak).
        resp = self._return(self.a_in_review.id)
        self.assertEqual(set(resp.data), {"id", "status"})
        self.assertEqual(resp.data["id"], self.a_in_review.id)
        self.assertEqual(resp.data["status"], "submitted")
        self.assertNotIn("iin", resp.data)
        blob = json.dumps(resp.data, ensure_ascii=False, default=str)
        self.assertEqual(re.findall(r"\b\d{12}\b", blob), [])

    @patch("eventproject.views.attendee_api.audit_log")
    def test_records_decision_audit_with_reason_and_from_to(self, mock_audit):
        resp = self._return(self.a_in_review.id)
        self.assertEqual(resp.status_code, 200)
        returned = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get("action") == "attendee.returned"
        ]
        self.assertEqual(len(returned), 1)
        extra = returned[0].kwargs["extra"]
        self.assertEqual(extra["from"], "in_review")
        self.assertEqual(extra["to"], "submitted")
        self.assertEqual(extra["reason"], REASON)

    def test_superuser_can_return(self):
        root = User.objects.create_superuser(
            username="root", password="StrongPass123!", email=""
        )
        client = APIClient()
        client.force_authenticate(root)
        resp = self._return(self.a_in_review.id, client=client)
        self.assertEqual(resp.status_code, 200)


class AttendeeReturnReasonRequiredTests(AttendeeReturnBase):
    def test_empty_reason_400_unchanged(self):
        resp = self._return(self.a_in_review.id, reason="")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["field"], "reason")
        self.a_in_review.refresh_from_db()
        self.assertEqual(self.a_in_review.status, "in_review")
        self.assertEqual(self.a_in_review.return_count, 0)

    def test_whitespace_reason_400(self):
        resp = self._return(self.a_in_review.id, reason="   ")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["field"], "reason")

    def test_missing_reason_400(self):
        resp = self._return(self.a_in_review.id, reason=None)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["field"], "reason")


class AttendeeReturnConflictGuardTests(AttendeeReturnBase):
    def test_return_draft_conflict_409_unchanged(self):
        resp = self._return(self.a_draft.id)
        self.assertEqual(resp.status_code, 409)
        self.a_draft.refresh_from_db()
        self.assertEqual(self.a_draft.status, "draft")

    def test_return_submitted_conflict_409(self):
        # submitted→submitted НЕ разрешён FSM (submitted→in_review только) → 409.
        resp = self._return(self.a_submitted.id)
        self.assertEqual(resp.status_code, 409)

    def test_return_ready_conflict_409(self):
        resp = self._return(self.a_ready.id)
        self.assertEqual(resp.status_code, 409)

    def test_return_exported_conflict_409(self):
        resp = self._return(self.a_exported.id)
        self.assertEqual(resp.status_code, 409)

    def test_conflict_carries_machine_code_envelope(self):
        # AC-1/AC-5: 409-тело несёт {type, field} в конверте fe-1.1 → FE-маппер fe-1.2 резолвит.
        resp = self._return(self.a_ready.id)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["type"], "status_transition_invalid")
        self.assertEqual(resp.data["field"], "status")

    @patch("eventproject.views.attendee_api.audit_log")
    def test_no_audit_on_conflict(self, mock_audit):
        self._return(self.a_ready.id)
        actions = [c.kwargs.get("action") for c in mock_audit.call_args_list]
        self.assertNotIn("attendee.returned", actions)


class AttendeeReturnRbacScopeTests(AttendeeReturnBase):
    def test_operator_forbidden_403_unchanged(self):
        client = APIClient()
        client.force_authenticate(self.op_user)
        resp = self._return(self.a_in_review.id, client=client)
        self.assertEqual(resp.status_code, 403)
        self.a_in_review.refresh_from_db()
        self.assertEqual(self.a_in_review.status, "in_review")

    def test_anonymous_denied(self):
        resp = self._return(self.a_in_review.id, client=APIClient())
        self.assertIn(resp.status_code, (401, 403))

    def test_unknown_id_404(self):
        resp = self._return(999999)
        self.assertEqual(resp.status_code, 404)

    def test_non_numeric_id_404(self):
        resp = self.client.post("/api/v1/attendees/abc/return/", {"reason": REASON}, format="json")
        self.assertEqual(resp.status_code, 404)
