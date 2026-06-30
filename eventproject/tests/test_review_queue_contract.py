"""Story fe-3.1 (AC-7) — backend-сторона контракт-артефакта очереди проверки.

Анти-дрейф: вывод `export_review_queue_fixture` == закоммиченный
`frontend/src/api/__fixtures__/review-queue.sample.json`. Если форма DTO
(`ReviewQueueSerializer`) изменится — фикстура краснеет, а не молча устаревает.
Дополняет vitest `reviewQueue.contract.test.ts` (zod-сторона). Прецедент — fe-1.1
`test_error_contract.py`. build_payload работает на in-memory заявках (без БД) →
SimpleTestCase.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from eventproject.management.commands.export_review_queue_fixture import (
    build_detail_payload,
    build_payload,
    serialize,
)
from eventproject.problem_flags import PROBLEM_FLAGS

_FIXTURE = (
    Path(settings.BASE_DIR) / "frontend" / "src" / "api" / "__fixtures__" / "review-queue.sample.json"
)
_DETAIL_FIXTURE = (
    Path(settings.BASE_DIR) / "frontend" / "src" / "api" / "__fixtures__" / "review-queue-detail.sample.json"
)


class ReviewQueueFixtureDriftTests(SimpleTestCase):
    def test_committed_fixture_matches_serializer_export(self):
        # Анти-дрейф: фикстура пересобирается командой 1:1 из живого сериализатора.
        self.assertTrue(
            _FIXTURE.exists(),
            "review-queue.sample.json отсутствует — запусти `manage.py export_review_queue_fixture`",
        )
        self.assertEqual(
            _FIXTURE.read_text(encoding="utf-8"),
            serialize(build_payload()),
            "review-queue.sample.json расходится с ReviewQueueSerializer — пере-экспортируй командой",
        )

    def test_fixture_shape_envelope_and_no_raw_iin(self):
        payload = build_payload()
        # Envelope пагинации DRF.
        self.assertEqual(set(payload), {"count", "next", "previous", "results"})
        self.assertEqual(payload["count"], len(payload["results"]))
        import json
        import re

        blob = json.dumps(payload, ensure_ascii=False)
        # Invariant-сканер: сырой 12-значный ИИН не появляется (только iin_masked).
        self.assertEqual(re.findall(r"\b\d{12}\b", blob), [])

    def test_fixture_problem_flags_cover_closed_enum(self):
        # Представимость: каждый член закрытого набора встречается в фикстуре.
        payload = build_payload()
        seen = set()
        for item in payload["results"]:
            seen.update(item["problem_flags"])
        self.assertEqual(seen, set(PROBLEM_FLAGS))


class ReviewQueueDetailFixtureDriftTests(SimpleTestCase):
    """fe-3.3 — анти-дрейф detail-фикстуры (ReviewQueueDetailSerializer)."""

    def test_committed_detail_fixture_matches_serializer_export(self):
        self.assertTrue(
            _DETAIL_FIXTURE.exists(),
            "review-queue-detail.sample.json отсутствует — запусти `manage.py export_review_queue_fixture`",
        )
        self.assertEqual(
            _DETAIL_FIXTURE.read_text(encoding="utf-8"),
            serialize(build_detail_payload()),
            "review-queue-detail.sample.json расходится с ReviewQueueDetailSerializer — пере-экспортируй командой",
        )

    def test_detail_shape_media_masked_iin_and_no_raw(self):
        payload = build_detail_payload()
        # detail = тонкий DTO списка + identity/медиа-поля; одиночный объект (не envelope).
        self.assertEqual(
            set(payload),
            {
                "id",
                "full_name",
                "iin_masked",
                "status",
                "sub_event_id",
                "sub_event_name",
                "problem_flags",
                "last_return_reason",
                "return_count",
                "photo",
                "doc_scan",
                "birth_date",
                "is_resident",
                "country",
                "post",
                "transcription",
                "doc_type",
                "created_at",
            },
        )
        # Маск-ИИН присутствует, сырого поля iin НЕТ.
        self.assertIn("iin_masked", payload)
        self.assertNotIn("iin", payload)
        # Медиа-ссылки на protected /media/ (или null).
        self.assertTrue(payload["photo"] is None or payload["photo"].startswith("/media/"))
        self.assertTrue(payload["doc_scan"] is None or payload["doc_scan"].startswith("/media/"))

    def test_detail_invariant_no_raw_iin(self):
        import json
        import re

        blob = json.dumps(build_detail_payload(), ensure_ascii=False, default=str)
        # Invariant-сканер: сырой 12-значный ИИН не появляется в detail-ответе.
        self.assertEqual(re.findall(r"\b\d{12}\b", blob), [])
