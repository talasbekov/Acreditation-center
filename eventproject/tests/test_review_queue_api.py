"""Story fe-3.1 — тесты DRF ReviewQueueViewSet (`GET /api/v1/review-queue/`).

Покрытие AC: RBAC (IsSuperoperator), очередь = submitted+in_review, scope-наследование
от резолвера (изоляция), DTO-форма + маск-ИИН + invariant-сканер, фильтры/400-кейсы,
представимость закрытого enum, популяция problem_flags при submit. Postgres-специфика
(Cyrillic icontains, JSON-containment фильтр) — под @skipUnless(postgresql).
"""

import json
import re
from unittest import skipUnless

from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from eventproject.models import Attendee, Event
from eventproject.problem_flags import PROBLEM_FLAGS
from eventproject.serializers.rbac import get_operator_attendee_queryset
from eventproject.tests.test_attendee_api import (
    BDATE,
    VALID_IIN,
    _make_attendee,
    _make_operator,
    _make_request,
)

_URL = "/api/v1/review-queue/"
_DTO_KEYS = {
    "id",
    "full_name",
    "iin_masked",
    "status",
    "sub_event_id",
    "sub_event_name",
    "problem_flags",
    "last_return_reason",
    "return_count",
}


class ReviewQueueApiBase(TestCase):
    def setUp(self):
        self.event1 = Event.objects.create(name_rus="Событие 1", title="E1")
        self.event2 = Event.objects.create(name_rus="Событие 2", title="E2")
        self.su_user, self.su = _make_operator("su", "superoperator")
        self.op_user, self.op = _make_operator("op", "operator", event=self.event1)
        self.req1 = _make_request(self.event1, self.op)
        self.req2 = _make_request(self.event2, self.su)
        # В очереди (submitted/in_review):
        self.a_submitted = _make_attendee(
            self.req1, surname="Алиев", status="submitted", iin=VALID_IIN
        )
        self.a_in_review = _make_attendee(
            self.req1, surname="Беков", status="in_review", iin=VALID_IIN
        )
        # НЕ в очереди:
        self.a_draft = _make_attendee(self.req1, surname="Драфтов", status="draft")
        self.a_ready = _make_attendee(self.req1, surname="Готовый", status="ready")
        # Чужое событие (агрегат для супероператора / изоляция для оператора):
        self.a_foreign = _make_attendee(
            self.req2, surname="Алиев", status="submitted", iin=VALID_IIN
        )
        self.client = APIClient()
        self.client.force_authenticate(self.su_user)


class ReviewQueueRbacTests(ReviewQueueApiBase):
    def test_superoperator_list_200_envelope(self):
        resp = self.client.get(_URL)
        self.assertEqual(resp.status_code, 200)
        for key in ("results", "count", "next", "previous"):
            self.assertIn(key, resp.data)

    def test_operator_forbidden_403(self):
        client = APIClient()
        client.force_authenticate(self.op_user)
        resp = client.get(_URL)
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_denied(self):
        resp = APIClient().get(_URL)
        self.assertIn(resp.status_code, (401, 403))


class ReviewQueueScopeTests(ReviewQueueApiBase):
    def test_queue_only_submitted_and_in_review(self):
        resp = self.client.get(_URL)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertIn(self.a_submitted.id, ids)
        self.assertIn(self.a_in_review.id, ids)
        self.assertNotIn(self.a_draft.id, ids)  # draft не в очереди
        self.assertNotIn(self.a_ready.id, ids)  # ready не в очереди

    def test_superoperator_sees_cross_event_aggregate(self):
        resp = self.client.get(_URL)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertIn(self.a_foreign.id, ids)  # чужое событие — виден супероператору

    def test_queue_queryset_inherits_operator_scope(self):
        # AC-6: scope — СТРУКТУРОЙ queryset (резолвер hd-5.3). Оператор event1 НЕ видит
        # заявку чужого события event2 — однофамилец «Алиев» отсечён структурой.
        ids = set(
            get_operator_attendee_queryset(self.op_user).values_list("id", flat=True)
        )
        self.assertIn(self.a_submitted.id, ids)
        self.assertNotIn(self.a_foreign.id, ids)


class ReviewQueueDtoTests(ReviewQueueApiBase):
    def test_dto_fields_exact(self):
        resp = self.client.get(_URL)
        row = next(r for r in resp.data["results"] if r["id"] == self.a_submitted.id)
        self.assertEqual(set(row), _DTO_KEYS)
        # Фабрика: surname="Алиев", firstname="Тест", patronymic=None → ФИО без отчества.
        self.assertEqual(row["full_name"], "Алиев Тест")
        self.assertEqual(row["iin_masked"], "********" + VALID_IIN[-4:])
        self.assertEqual(row["sub_event_id"], self.event1.id)
        self.assertEqual(row["sub_event_name"], "Событие 1")
        self.assertIsNone(row["last_return_reason"])
        self.assertEqual(row["return_count"], 0)

    def test_live_envelope_keys_match_committed_fixture(self):
        # AC-7/B2: ключи envelope живого пагинатора == закоммиченная golden-fixture
        # (фикстура собирается вручную в export-команде → доказываем, что она не
        # расходится с реальным StandardResultsSetPagination).
        from pathlib import Path

        from django.conf import settings

        fixture = json.loads(
            (
                Path(settings.BASE_DIR)
                / "frontend"
                / "src"
                / "api"
                / "__fixtures__"
                / "review-queue.sample.json"
            ).read_text(encoding="utf-8")
        )
        resp = self.client.get(_URL)
        self.assertEqual(set(resp.data.keys()), set(fixture.keys()))

    def test_invariant_no_raw_iin_in_response(self):
        # AC-4: сырой 12-значный ИИН не появляется ни в одной ветке ответа.
        resp = self.client.get(_URL)
        blob = json.dumps(resp.data, ensure_ascii=False, default=str)
        self.assertEqual(re.findall(r"\b\d{12}\b", blob), [])

    def test_dto_carries_full_closed_enum(self):
        # AC-2: представимость — DTO несёт любой подмножество закрытого набора.
        self.a_submitted.problem_flags = list(PROBLEM_FLAGS)
        self.a_submitted.save(update_fields=["problem_flags"])
        resp = self.client.get(_URL)
        row = next(r for r in resp.data["results"] if r["id"] == self.a_submitted.id)
        self.assertEqual(row["problem_flags"], list(PROBLEM_FLAGS))


class ReviewQueueFilterTests(ReviewQueueApiBase):
    def test_filter_sub_event_id_valid(self):
        resp = self.client.get(_URL, {"sub_event_id": self.event1.id})
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertIn(self.a_submitted.id, ids)
        self.assertNotIn(self.a_foreign.id, ids)  # event2 отфильтрован

    def test_filter_sub_event_id_non_int_400(self):
        resp = self.client.get(_URL, {"sub_event_id": "abc"})
        self.assertEqual(resp.status_code, 400)

    def test_filter_sub_event_id_empty_400(self):
        resp = self.client.get(_URL, {"sub_event_id": ""})
        self.assertEqual(resp.status_code, 400)

    def test_filter_sub_event_id_unknown_returns_empty_not_404(self):
        resp = self.client.get(_URL, {"sub_event_id": 999999})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)

    def test_filter_problem_bogus_400(self):
        resp = self.client.get(_URL, {"problem": "__bogus__"})
        self.assertEqual(resp.status_code, 400)

    def test_filter_problem_empty_400(self):
        resp = self.client.get(_URL, {"problem": ""})
        self.assertEqual(resp.status_code, 400)

    def test_filter_status_narrow_submitted(self):
        resp = self.client.get(_URL, {"status": "submitted"})
        self.assertEqual(resp.status_code, 200)
        statuses = {r["status"] for r in resp.data["results"]}
        self.assertTrue(statuses <= {"submitted"})
        self.assertNotIn(self.a_in_review.id, {r["id"] for r in resp.data["results"]})

    def test_filter_status_outside_queue_400(self):
        # ready — валидный статус, но НЕ в очереди → 400 (сужение только submitted|in_review).
        resp = self.client.get(_URL, {"status": "ready"})
        self.assertEqual(resp.status_code, 400)

    def test_filter_status_bogus_400(self):
        resp = self.client.get(_URL, {"status": "__nope__"})
        self.assertEqual(resp.status_code, 400)

    def test_filter_status_empty_400(self):
        resp = self.client.get(_URL, {"status": ""})
        self.assertEqual(resp.status_code, 400)

    def test_search_by_name(self):
        resp = self.client.get(_URL, {"search": "Беков"})
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertIn(self.a_in_review.id, ids)
        self.assertNotIn(self.a_submitted.id, ids)

    @skipUnless(
        connection.vendor == "postgresql",
        "Кейс-фолдинг кириллицы в icontains только на Postgres (prod); SQLite LIKE ASCII-only.",
    )
    def test_search_cyrillic_case_insensitive(self):
        resp = self.client.get(_URL, {"search": "беков"})
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertIn(self.a_in_review.id, ids)

    def test_filter_problem_valid(self):
        # Портируемый фильтр (Cast→TextField + icontains) → тест идёт и на SQLite (CI).
        self.a_submitted.problem_flags = ["no_photo"]
        self.a_submitted.save(update_fields=["problem_flags"])
        resp = self.client.get(_URL, {"problem": "no_photo"})
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertIn(self.a_submitted.id, ids)
        self.assertNotIn(self.a_in_review.id, ids)

    def test_filter_problem_no_false_positive_substring(self):
        # Кавыченное совпадение: ?problem=photo_ratio НЕ матчит строку с "no_photo".
        self.a_submitted.problem_flags = ["no_photo"]
        self.a_submitted.save(update_fields=["problem_flags"])
        resp = self.client.get(_URL, {"problem": "photo_ratio"})
        self.assertEqual(resp.status_code, 200)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertNotIn(self.a_submitted.id, ids)


class ReviewQueueDetailTests(ReviewQueueApiBase):
    """fe-3.3 — retrieve (`GET /api/v1/review-queue/{id}/`) — detail-DTO экрана заявки."""

    _DETAIL_KEYS = _DTO_KEYS | {
        "photo",
        "doc_scan",
        "birth_date",
        "is_resident",
        "country",
        "post",
        "transcription",
        "doc_type",
        "created_at",
    }

    def test_detail_retrieve_200_shape_and_masked_iin(self):
        resp = self.client.get(f"{_URL}{self.a_submitted.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.data), self._DETAIL_KEYS)
        # Маск-ИИН (не сырой), статус, медиа-ключи присутствуют.
        self.assertEqual(resp.data["iin_masked"], "********" + VALID_IIN[-4:])
        self.assertNotIn("iin", resp.data)
        self.assertEqual(resp.data["status"], "submitted")
        self.assertIn("photo", resp.data)
        self.assertIn("doc_scan", resp.data)

    def test_detail_invariant_no_raw_iin(self):
        resp = self.client.get(f"{_URL}{self.a_submitted.id}/")
        blob = json.dumps(resp.data, ensure_ascii=False, default=str)
        self.assertEqual(re.findall(r"\b\d{12}\b", blob), [])

    def test_detail_draft_not_in_queue_404(self):
        # draft вне очереди (submitted+in_review) → выпадает из queryset → 404.
        resp = self.client.get(f"{_URL}{self.a_draft.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_detail_ready_not_in_queue_404(self):
        resp = self.client.get(f"{_URL}{self.a_ready.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_detail_unknown_id_404(self):
        resp = self.client.get(f"{_URL}999999/")
        self.assertEqual(resp.status_code, 404)

    def test_detail_operator_forbidden_403(self):
        # IsSuperoperator: оператор не имеет доступа к detail очереди (как и к списку).
        client = APIClient()
        client.force_authenticate(self.op_user)
        resp = client.get(f"{_URL}{self.a_submitted.id}/")
        self.assertEqual(resp.status_code, 403)


class ReviewQueueSubmitFlagsTests(ReviewQueueApiBase):
    def test_submit_populates_problem_flags(self):
        # AC-2: при submit заявки флаги вычисляются и хранятся (compute_problem_flags).
        op_client = APIClient()
        op_client.force_authenticate(self.op_user)
        event3 = Event.objects.create(name_rus="Событие 3")
        self.op.events.add(event3)
        req3 = _make_request(event3, self.op)
        # Валидный ИИН + без фото + событие без дублей → ровно ["no_photo"].
        draft = _make_attendee(
            req3, surname="Сабмитов", status="draft", iin=VALID_IIN, birthDate=BDATE
        )
        resp = op_client.post(f"/api/v1/attendees/{draft.id}/submit/")
        self.assertEqual(resp.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "submitted")
        self.assertEqual(draft.problem_flags, ["no_photo"])
