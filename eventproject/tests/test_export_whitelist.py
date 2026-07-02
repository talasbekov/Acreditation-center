"""Story hd-1.1 — whitelist-сериализатор легаси JSON-экспорта (file_download.py).

Гэп: file_download.py строил JSON через model_to_dict() — дамп всех полей модели
(расшифрованный ИИН, служебные review-workflow поля). Этот модуль тестирует явный
whitelist-билдер serializers/export.py: закрытый набор ключей (set-equality — ловит
и лишний, и утраченный ключ) + invariant-сканер ИИН по сериализованному телу.

Премиса-конфликт (см. story Dev Notes): services/export.py (Integration Spec v1.0,
resident-ИИН, подтверждено Erda 2026-06-23) этой историей НЕ трогается — здесь
тестируется только НОВЫЙ легаси-путь.
"""

import json
import re

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from directories.models import Country, DocumentType, Sex
from eventproject.models import Attendee, Event, Operator, Request
from eventproject.serializers.export import (
    LEGACY_ATTENDEE_FIELDS,
    LEGACY_EVENT_FIELDS,
    LEGACY_REQUEST_FIELDS,
    LEGACY_SCHEMA_VERSION,
    build_legacy_attendee_dict,
    build_legacy_event_dict,
    build_legacy_request_dict,
)

IIN_PATTERN = re.compile(r"\b\d{12}\b")
KZ = "1000000105"


class LegacyWhitelistBuilderTests(TestCase):
    def setUp(self):
        Country.objects.create(country_code=KZ, name_rus="Казахстан", name_kaz="", name_eng="", country_iso="KZ")
        Sex.objects.create(sex_code="M", name_rus="Мужской", name_kaz="", name_eng="")
        DocumentType.objects.create(doc_code="passport", name_rus="Паспорт", name_kaz="", name_eng="")

        self.event = Event.objects.create(
            name_rus="Событие", name_kaz="Оқиға", name_eng="Event",
            event_code="EXP01", city_code="ALA",
        )
        op_user = User.objects.create_user(username="op", password="pw12345678")
        self.operator = Operator.objects.create(
            user=op_user, patronymic="T", phone_number="+77001234567",
            workplace="office", role="operator",
        )
        self.request_obj = Request.objects.create(
            name="Охрана", event=self.event, status="Sent",
            created_by=self.operator, registration_time=timezone.now(),
        )
        self.attendee = Attendee.objects.create(
            surname="Иванов", firstname="Иван", patronymic="Иванович",
            birthDate="1990-01-01", post="Инженер", countryId=KZ,
            docTypeId="passport", docSeries="AA", docNumber="123456",
            docIssue="МВД", sexId="M", visitObjects="Зал",
            transcription="Ivanov Ivan", request=self.request_obj,
            iin="900101300007", is_resident=True, status="ready",
            photo="photos/1.jpg", docScan="documents/1.jpg",
            dateAdd=timezone.now(),
        )

    def test_attendee_dict_key_set_is_exact(self):
        """AC-2: set-equality — ловит и лишний, и утраченный ключ."""
        obj = build_legacy_attendee_dict(self.attendee)
        self.assertEqual(set(obj.keys()), LEGACY_ATTENDEE_FIELDS)

    def test_attendee_dict_excludes_iin(self):
        obj = build_legacy_attendee_dict(self.attendee)
        self.assertNotIn("iin", obj)

    def test_attendee_dict_excludes_internal_review_fields(self):
        obj = build_legacy_attendee_dict(self.attendee)
        for field in ("problem_flags", "last_return_reason", "return_count", "stickId"):
            self.assertNotIn(field, obj)

    def test_attendee_dict_iin_invariant_scanner(self):
        """Сериализованное тело не содержит ИИН ни в одном значении (не только ключе)."""
        obj = build_legacy_attendee_dict(self.attendee)
        body = json.dumps(obj, ensure_ascii=False)
        self.assertNotRegex(body, IIN_PATTERN)

    def test_attendee_dict_specific_db_iin_value_not_leaked(self):
        """Негативный тест не только по regex: конкретное значение ИИН из БД
        (расшифрованное) отсутствует в сериализованном теле дословно."""
        stored_iin = self.attendee.iin
        self.assertEqual(stored_iin, "900101300007")  # sanity: ИИН реально в БД/расшифрован
        obj = build_legacy_attendee_dict(self.attendee)
        body = json.dumps(obj, ensure_ascii=False)
        self.assertNotIn(stored_iin, body)

    def test_attendee_dict_preserves_expected_values(self):
        obj = build_legacy_attendee_dict(self.attendee)
        self.assertEqual(obj["surname"], "Иванов")
        self.assertEqual(obj["firstname"], "Иван")
        self.assertEqual(obj["status"], "ready")
        self.assertEqual(obj["is_resident"], True)
        self.assertEqual(obj["birth_date"], "01.01.1990")
        self.assertEqual(obj["schema_version"], LEGACY_SCHEMA_VERSION)

    def test_attendee_dict_non_resident_still_has_no_iin(self):
        self.attendee.is_resident = False
        self.attendee.save()
        obj = build_legacy_attendee_dict(self.attendee)
        self.assertNotIn("iin", obj)

    def test_event_dict_key_set_is_exact(self):
        obj = build_legacy_event_dict(self.event)
        self.assertEqual(set(obj.keys()), LEGACY_EVENT_FIELDS)

    def test_event_dict_preserves_expected_values(self):
        obj = build_legacy_event_dict(self.event)
        self.assertEqual(obj["event_code"], "EXP01")
        self.assertEqual(obj["name_rus"], "Событие")
        self.assertEqual(obj["schema_version"], LEGACY_SCHEMA_VERSION)

    def test_event_dict_falls_back_to_story22_fields_when_legacy_null(self):
        """Событие, созданное через REST (EventSerializer, Story 2.2), пишет только
        title/start_date/end_date — legacy name_rus/date_start остаются NULL. Без
        coalesce шапка экспорта уходила бы пустой (review hd-1.1, Edge Case Hunter)."""
        rest_event = Event.objects.create(
            title="REST Event", start_date="2026-08-01", end_date="2026-08-03",
        )
        obj = build_legacy_event_dict(rest_event)
        self.assertEqual(obj["name_rus"], "REST Event")
        self.assertEqual(obj["name_kaz"], "REST Event")
        self.assertEqual(obj["name_eng"], "REST Event")
        self.assertEqual(obj["date_start"], "01.08.2026")
        self.assertEqual(obj["date_end"], "03.08.2026")

    def test_event_dict_legacy_fields_win_when_both_present(self):
        obj = build_legacy_event_dict(self.event)
        # self.event только с legacy-полями (title/start_date/end_date не заданы) —
        # legacy-значения должны остаться, а не быть перезаписаны None-фоллбэком.
        self.assertEqual(obj["name_rus"], "Событие")
        self.assertEqual(obj["date_start"], None)  # у фикстуры date_start не задан

    def test_request_dict_key_set_is_exact(self):
        obj = build_legacy_request_dict(self.request_obj)
        self.assertEqual(set(obj.keys()), LEGACY_REQUEST_FIELDS)

    def test_request_dict_preserves_expected_values(self):
        obj = build_legacy_request_dict(self.request_obj)
        self.assertEqual(obj["name"], "Охрана")
        self.assertEqual(obj["status"], "Sent")
        self.assertEqual(obj["created_by_id"], self.operator.id)
        self.assertEqual(obj["schema_version"], LEGACY_SCHEMA_VERSION)

    def test_attendee_dict_media_url_none_when_file_missing_on_disk(self):
        """_media_url проверяет существование на диске (mirror _add_media D5) —
        self.attendee.photo/docScan указывают на несуществующие файлы (фикстура)."""
        obj = build_legacy_attendee_dict(self.attendee)
        self.assertIsNone(obj["photo_url"])
        self.assertIsNone(obj["doc_scan_url"])

    def test_attendee_dict_media_url_present_when_file_exists(self):
        self.attendee.photo = SimpleUploadedFile(
            "real.jpg", b"\xff\xd8\xff" + b"0" * 100, content_type="image/jpeg"
        )
        self.attendee.save()
        obj = build_legacy_attendee_dict(self.attendee)
        self.assertIsNotNone(obj["photo_url"])
        self.assertIn("real", obj["photo_url"])

    def test_attendee_dict_media_url_absolute_with_request(self):
        from django.test import RequestFactory

        self.attendee.photo = SimpleUploadedFile(
            "abs.jpg", b"\xff\xd8\xff" + b"0" * 100, content_type="image/jpeg"
        )
        self.attendee.save()
        request = RequestFactory().get("/download_json/1/")
        obj = build_legacy_attendee_dict(self.attendee, request=request)
        self.assertTrue(obj["photo_url"].startswith("http://"))


class LegacyExportEndpointWhitelistTests(TestCase):
    """AC-1/AC-2: 4 живых легаси-эндпоинта отдают whitelist, не model_to_dict."""

    def setUp(self):
        Country.objects.create(country_code=KZ, name_rus="Казахстан", name_kaz="", name_eng="", country_iso="KZ")
        Sex.objects.create(sex_code="M", name_rus="Мужской", name_kaz="", name_eng="")
        DocumentType.objects.create(doc_code="passport", name_rus="Паспорт", name_kaz="", name_eng="")

        self.superuser = User.objects.create_superuser(
            username="su", password="pw12345678", email="su@example.com"
        )
        op_user = User.objects.create_user(username="op2", password="pw12345678")
        self.operator = Operator.objects.create(
            user=op_user, patronymic="T", phone_number="+77001234567",
            workplace="office", role="operator",
        )
        self.event = Event.objects.create(
            name_rus="Событие", name_kaz="Оқиға", name_eng="Event",
            event_code="EXP02", city_code="ALA",
        )
        self.request_obj = Request.objects.create(
            name="Охрана", event=self.event, status="Sent",
            created_by=self.operator, registration_time=timezone.now(),
        )
        self.attendee = Attendee.objects.create(
            surname="Петров", firstname="Пётр", patronymic="Петрович",
            birthDate="1985-05-05", post="Инженер", countryId=KZ,
            docTypeId="passport", docSeries="AA", docNumber="654321",
            docIssue="МВД", sexId="M", visitObjects="Зал",
            transcription="Petrov Petr", request=self.request_obj,
            iin="850505300007", is_resident=True, status="ready",
            dateAdd=timezone.now(),
        )
        self.client.force_login(self.superuser)

    def _assert_body_whitelisted(self, resp):
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertNotRegex(body, IIN_PATTERN)
        self.assertNotIn(self.attendee.iin, body)  # негативный тест не только по regex
        self.assertIn("Петров", body)
        payload = json.loads(body)
        return payload

    def test_download_json_excludes_iin(self):
        resp = self.client.post(f"/download_json/{self.event.id}/")
        payload = self._assert_body_whitelisted(resp)
        self.assertEqual(set(payload["attendees"][0].keys()), LEGACY_ATTENDEE_FIELDS)
        self.assertEqual(set(payload.keys()), LEGACY_EVENT_FIELDS | {"attendees"})

    def test_download_guests_json_excludes_iin(self):
        resp = self.client.post(f"/download_guests_json/{self.event.id}/")
        payload = self._assert_body_whitelisted(resp)
        self.assertEqual(set(payload["attendees"][0].keys()), LEGACY_ATTENDEE_FIELDS)

    def test_download_all_guests_json_excludes_iin(self):
        resp = self.client.post(f"/download_all_guests_json/{self.event.id}/")
        payload = self._assert_body_whitelisted(resp)
        self.assertEqual(set(payload["attendees"][0].keys()), LEGACY_ATTENDEE_FIELDS)

    def test_download_request_json_excludes_iin(self):
        resp = self.client.post(f"/download_request_json/{self.request_obj.id}/")
        payload = self._assert_body_whitelisted(resp)
        self.assertEqual(set(payload["attendees"][0].keys()), LEGACY_ATTENDEE_FIELDS)
        self.assertEqual(payload["event"]["event_code"], "EXP02")
        self.assertEqual(set(payload.keys()), LEGACY_REQUEST_FIELDS | {"attendees", "event"})

    def test_download_request_json_event_is_whitelisted_dict_not_raw_object(self):
        """Регресс: request_dict['event'] был сырым Event-объектом (default=str-костыль)."""
        resp = self.client.post(f"/download_request_json/{self.request_obj.id}/")
        payload = self._assert_body_whitelisted(resp)
        self.assertEqual(set(payload["event"].keys()), LEGACY_EVENT_FIELDS)
