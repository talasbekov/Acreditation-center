"""Story fe-3.4 — тесты approve-экшена AttendeeViewSet (`POST /attendees/{id}/approve/`).

Покрытие AC:
  • AC-1 — FSM in_review→ready, save(update_fields), audit через _record_decision,
    409-guard на не-in_review, masked-safe ответ {id,status} (реш.#6: НЕ AttendeeSerializer).
  • AC-2 — RBAC IsSuperoperator (оператор→403, аноним→401/403), scope/404 (неизвестный id).
  • AC-5 — 409-тело несёт машинный код в конверте fe-1.1 ({type, params, field}).

approve — на AttendeeViewSet (не review-queue): scope наследуется от
get_operator_attendee_queryset (hd-5.3). Mirror submit-экшена, но цель READY и 409≠400.
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


class AttendeeApproveBase(TestCase):
    def setUp(self):
        self.event1 = Event.objects.create(name_rus="Событие 1", title="E1")
        self.su_user, self.su = _make_operator("su", "superoperator")
        self.op_user, self.op = _make_operator("op", "operator", event=self.event1)
        self.req1 = _make_request(self.event1, self.op)
        # По одному участнику на каждый исходный статус.
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

    def _approve(self, attendee_id, client=None):
        return (client or self.client).post(f"/api/v1/attendees/{attendee_id}/approve/")


class AttendeeApproveHappyPathTests(AttendeeApproveBase):
    def test_approve_in_review_to_ready_200(self):
        resp = self._approve(self.a_in_review.id)
        self.assertEqual(resp.status_code, 200)
        self.a_in_review.refresh_from_db()
        self.assertEqual(self.a_in_review.status, "ready")

    def test_response_is_masked_safe_no_raw_iin(self):
        # реш.#6: ответ = {id, status} (минимально), НЕ AttendeeSerializer (сырой ИИН leak).
        resp = self._approve(self.a_in_review.id)
        self.assertEqual(set(resp.data), {"id", "status"})
        self.assertEqual(resp.data["id"], self.a_in_review.id)
        self.assertEqual(resp.data["status"], "ready")
        self.assertNotIn("iin", resp.data)
        blob = json.dumps(resp.data, ensure_ascii=False, default=str)
        self.assertEqual(re.findall(r"\b\d{12}\b", blob), [])

    @patch("eventproject.views.attendee_api.audit_log")
    def test_records_decision_audit_with_from_to(self, mock_audit):
        resp = self._approve(self.a_in_review.id)
        self.assertEqual(resp.status_code, 200)
        approved = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get("action") == "attendee.approved"
        ]
        self.assertEqual(len(approved), 1)
        extra = approved[0].kwargs["extra"]
        self.assertEqual(extra["from"], "in_review")
        self.assertEqual(extra["to"], "ready")

    def test_superuser_can_approve(self):
        root = User.objects.create_superuser(
            username="root", password="StrongPass123!", email=""
        )
        client = APIClient()
        client.force_authenticate(root)
        resp = self._approve(self.a_in_review.id, client=client)
        self.assertEqual(resp.status_code, 200)


class AttendeeApproveConflictGuardTests(AttendeeApproveBase):
    def test_approve_draft_conflict_409_unchanged(self):
        resp = self._approve(self.a_draft.id)
        self.assertEqual(resp.status_code, 409)
        self.a_draft.refresh_from_db()
        self.assertEqual(self.a_draft.status, "draft")

    def test_approve_submitted_conflict_409(self):
        # submitted→ready НЕ разрешён FSM (submitted→in_review только) → 409, не двойной переход.
        resp = self._approve(self.a_submitted.id)
        self.assertEqual(resp.status_code, 409)

    def test_approve_ready_conflict_409(self):
        # terminal-ish: ready уже одобрена → повторное одобрение = конфликт.
        resp = self._approve(self.a_ready.id)
        self.assertEqual(resp.status_code, 409)

    def test_approve_exported_conflict_409_unchanged(self):
        # review P6 — exported терминальный (ALLOWED_TRANSITIONS[exported]=∅): approve = 409,
        # не переход. Граница покрыта регрессией (раньше тестов был только draft/submitted/ready).
        resp = self._approve(self.a_exported.id)
        self.assertEqual(resp.status_code, 409)
        self.a_exported.refresh_from_db()
        self.assertEqual(self.a_exported.status, "exported")

    def test_conflict_carries_machine_code_envelope(self):
        # AC-5: тело несёт {type, field} в конверте fe-1.1 → FE-маппер fe-1.2 резолвит (не 400).
        resp = self._approve(self.a_ready.id)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["type"], "status_transition_invalid")
        self.assertEqual(resp.data["field"], "status")

    @patch("eventproject.views.attendee_api.audit_log")
    def test_no_audit_on_conflict(self, mock_audit):
        self._approve(self.a_ready.id)
        actions = [c.kwargs.get("action") for c in mock_audit.call_args_list]
        self.assertNotIn("attendee.approved", actions)


class AttendeeApproveRbacScopeTests(AttendeeApproveBase):
    def test_operator_forbidden_403_unchanged(self):
        client = APIClient()
        client.force_authenticate(self.op_user)
        resp = self._approve(self.a_in_review.id, client=client)
        self.assertEqual(resp.status_code, 403)
        self.a_in_review.refresh_from_db()
        self.assertEqual(self.a_in_review.status, "in_review")

    def test_anonymous_denied(self):
        resp = self._approve(self.a_in_review.id, client=APIClient())
        self.assertIn(resp.status_code, (401, 403))

    def test_unknown_id_404(self):
        # scope/404 наследуется от get_operator_attendee_queryset (не палим существование).
        resp = self._approve(999999)
        self.assertEqual(resp.status_code, 404)

    def test_non_numeric_id_404(self):
        # review P8 (AC-2) — нечисловой pk → стандартный 404 роутера/DRF (не 500), как у
        # существующих detail-экшенов. Раньше покрывался только числовой out-of-scope id.
        resp = self.client.post("/api/v1/attendees/abc/approve/")
        self.assertEqual(resp.status_code, 404)
