"""Story 4.3 — тесты delta-экспорта (serializer, delta-выборка, ZIP, ExportLog, RBAC, backfill)."""

import importlib
import io
import json
import tempfile
import zipfile
from datetime import timedelta

from django.apps import apps
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from directories.models import Country, DocumentType, Sex
from eventproject.models import Attendee, Category, Event, ExportLog, Operator, Request
from eventproject.services import export as export_service
from eventproject.tests.test_export_contract import load_spec_schema, validate_against_spec

KZ = "1000000105"
NON_KZ = "1000000840"


class ExportDeltaBase(TestCase):
    def setUp(self):
        # Справочники для resolve *_name.
        Country.objects.create(country_code=KZ, name_rus="Казахстан", name_kaz="", name_eng="", country_iso="KZ")
        Sex.objects.create(sex_code="M", name_rus="Мужской", name_kaz="", name_eng="")
        DocumentType.objects.create(doc_code="passport", name_rus="Паспорт", name_kaz="", name_eng="")

        self.event = Event.objects.create(name_rus="E1", title="Event 1", event_code="T1")

        self.super_user = User.objects.create_user("super", password="Pass123!")
        Operator.objects.create(
            user=self.super_user, role="superoperator", patronymic="С",
            phone_number="+70000000001", workplace="HQ",
        )
        self.op_user = User.objects.create_user("op", password="Pass123!")
        self.operator = Operator.objects.create(
            user=self.op_user, role="operator", patronymic="О",
            phone_number="+70000000002", workplace="HQ",
        )
        self.category = Request.objects.create(
            name="Охрана", event=self.event, status="Sent", created_by=self.operator,
            registration_time=timezone.now(),
        )

    def _mk(self, status, *, is_resident=True, iin="900101300007", photo="img.jpg",
            doc="img.jpg", request=None, dateAdd=None, **over):
        data = dict(
            surname="Тест", firstname="Имя", post="P",
            countryId=KZ if is_resident else NON_KZ,
            docTypeId="passport", docSeries="AA", docIssue="МВД", sexId="M",
            visitObjects="Зал", transcription="T", request=request or self.category,
            dateAdd=dateAdd or timezone.now(), status=status, is_resident=is_resident,
            iin=iin, photo=photo, docScan=doc,
        )
        data.update(over)
        return Attendee.objects.create(**data)

    def _url(self):
        return f"/export_delta/{self.event.id}/{self.category.id}/"


class BuildExportObjectTests(ExportDeltaBase):
    def test_object_matches_spec_v1(self):
        a = self._mk("ready", is_resident=True, iin="900101300007", birthDate="1990-01-01")
        obj = export_service.build_export_object(a)
        errors = validate_against_spec(obj, load_spec_schema())
        self.assertEqual(errors, [], f"export object не соответствует Spec v1.0: {errors}")
        self.assertEqual(obj["country_name"], "Казахстан")
        self.assertEqual(obj["sex_name"], "Мужской")
        self.assertEqual(obj["doc_type_name"], "Паспорт")
        self.assertEqual(obj["iin"], "900101300007")
        self.assertEqual(obj["birth_date"], "01.01.1990")  # формат DD.MM.YYYY
        self.assertEqual(obj["photo_file"], f"photos/{a.id}.jpg")

    def test_non_resident_iin_null(self):
        a = self._mk("ready", is_resident=False, iin=None)
        obj = export_service.build_export_object(a)
        self.assertIsNone(obj["iin"])
        errors = validate_against_spec(obj, load_spec_schema())
        self.assertEqual(errors, [], f"нерезидент: {errors}")

    def test_unknown_directory_code_name_null(self):
        a = self._mk("ready", sexId="X")  # кода нет в справочнике
        obj = export_service.build_export_object(a)
        self.assertIsNone(obj["sex_name"])
        errors = validate_against_spec(obj, load_spec_schema())
        self.assertEqual(errors, [], f"unknown code: {errors}")

    def test_object_with_category_matches_spec(self):
        # ревью 4.3 (AC-6): участник с заполненной категорией использует category.name
        # (у eventproject.Category нет name_rus). Без этого кейса CRITICAL был замаскирован.
        cat = Category.objects.create(event=self.event, name="Охрана")
        a = self._mk("ready", category=cat)
        obj = export_service.build_export_object(a)
        self.assertEqual(obj["category"], "Охрана")
        errors = validate_against_spec(obj, load_spec_schema())
        self.assertEqual(errors, [], f"категоризированный участник: {errors}")


class DeltaSelectionTests(ExportDeltaBase):
    def test_first_export_selects_all_ready(self):
        self._mk("ready"); self._mk("ready"); self._mk("draft")
        qs = export_service.select_new_attendees(self.category, None, timezone.now())
        self.assertEqual(qs.count(), 2)

    def test_excludes_non_ready(self):
        self._mk("draft"); self._mk("submitted"); self._mk("exported")
        qs = export_service.select_new_attendees(self.category, None, timezone.now())
        self.assertEqual(list(qs), [])

    def test_second_export_only_new(self):
        old = self._mk("ready", dateAdd=timezone.now() - timedelta(hours=2))
        boundary = timezone.now() - timedelta(hours=1)
        new = self._mk("ready", dateAdd=timezone.now())
        qs = export_service.select_new_attendees(self.category, boundary, timezone.now())
        self.assertEqual(list(qs.values_list("id", flat=True)), [new.id])

    def test_other_category_excluded(self):
        other = Request.objects.create(
            name="Гости", event=self.event, status="Sent", created_by=self.operator,
            registration_time=timezone.now(),
        )
        self._mk("ready", request=other)
        mine = self._mk("ready")
        qs = export_service.select_new_attendees(self.category, None, timezone.now())
        self.assertEqual(list(qs.values_list("id", flat=True)), [mine.id])


class ExportViewTests(ExportDeltaBase):
    def test_export_creates_log_transitions_and_audits(self):
        a1 = self._mk("ready"); a2 = self._mk("ready")
        self.client.force_login(self.super_user)
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")
        b"".join(resp.streaming_content)  # дренируем поток
        self.assertEqual(ExportLog.objects.count(), 1)
        log = ExportLog.objects.get()
        self.assertEqual(log.category_id, self.category.id)
        self.assertEqual(log.event_id, self.event.id)
        self.assertEqual(log.attendee_count, 2)
        self.assertEqual(log.user_id, self.super_user.id)
        a1.refresh_from_db(); a2.refresh_from_db()
        self.assertEqual(a1.status, "exported")
        self.assertEqual(a2.status, "exported")

    def test_second_export_returns_only_new(self):
        a_old = self._mk("ready")
        self.client.force_login(self.super_user)
        b"".join(self.client.post(self._url()).streaming_content)  # первый экспорт
        a_new = self._mk("ready")  # добавлен после
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 200)
        content = b"".join(resp.streaming_content)
        data = json.loads(zipfile.ZipFile(io.BytesIO(content)).read("attendees.json"))
        ids = [o["attendee_id"] for o in data]
        self.assertEqual(ids, [a_new.id])  # только новый, не a_old
        self.assertEqual(ExportLog.objects.count(), 2)

    def test_no_new_records_first_time(self):
        self._mk("draft")  # нет ready
        self.client.force_login(self.super_user)
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Нет записей", resp.content.decode())
        self.assertEqual(ExportLog.objects.count(), 0)

    def test_no_new_records_after_export_shows_date(self):
        ExportLog.objects.create(
            event=self.event, category=self.category, exported_before=timezone.now(),
            user=self.super_user, attendee_count=1,
        )
        self._mk("ready", dateAdd=timezone.now() - timedelta(hours=1))  # старее границы
        self.client.force_login(self.super_user)
        resp = self.client.post(self._url())
        self.assertIn("Нет новых записей с момента последнего экспорта", resp.content.decode())
        self.assertEqual(ExportLog.objects.count(), 1)  # новый не создан

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_zip_contains_json_and_media(self):
        photo = SimpleUploadedFile("p.jpg", b"\xff\xd8\xff" + b"0" * 1500, content_type="image/jpeg")
        doc = SimpleUploadedFile("d.jpg", b"\xff\xd8\xff" + b"0" * 1500, content_type="image/jpeg")
        a = self._mk("ready", photo=photo, doc=doc)
        self.client.force_login(self.super_user)
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 200)
        content = b"".join(resp.streaming_content)
        zf = zipfile.ZipFile(io.BytesIO(content))
        names = zf.namelist()
        self.assertIn("attendees.json", names)
        self.assertIn(f"photos/{a.id}.jpg", names)
        self.assertIn(f"documents/{a.id}.jpg", names)
        data = json.loads(zf.read("attendees.json"))
        self.assertEqual(data[0]["attendee_id"], a.id)

    def test_export_blocked_when_event_code_missing(self):
        # D4 (ревью 4.3): event_code обязателен по контракту v1.0 → 400, ExportLog не создаётся.
        self.event.event_code = None
        self.event.save()
        self._mk("ready")
        self.client.force_login(self.super_user)
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ExportLog.objects.count(), 0)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_zip_missing_media_nulls_path(self):
        # D5 (ревью 4.3): файла нет на диске → photo_file/doc_scan_file = null (не битая
        # ссылка); архивный attendees.json остаётся валидным по схеме (media nullable).
        a = self._mk("ready", photo="ghost.jpg", doc="ghost.jpg")  # имена есть, файлов нет
        self.client.force_login(self.super_user)
        resp = self.client.post(self._url())
        content = b"".join(resp.streaming_content)
        zf = zipfile.ZipFile(io.BytesIO(content))
        self.assertNotIn(f"photos/{a.id}.jpg", zf.namelist())
        self.assertNotIn(f"documents/{a.id}.jpg", zf.namelist())
        data = json.loads(zf.read("attendees.json"))
        self.assertIsNone(data[0]["photo_file"])
        self.assertIsNone(data[0]["doc_scan_file"])
        errors = validate_against_spec(data[0], load_spec_schema())
        self.assertEqual(errors, [], f"archived json должен быть валиден: {errors}")

    def test_anonymous_redirected(self):
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 302)

    def test_operator_forbidden(self):
        self.client.force_login(self.op_user)
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 403)


class BackfillStatusMigrationTests(ExportDeltaBase):
    def test_backfill_maps_request_status(self):
        mod = importlib.import_module("eventproject.migrations.0022_backfill_attendee_status")
        mapping = {
            "Active": "draft", "Checking": "in_review", "Sent": "ready",
            "Exported": "exported", "completed": "exported",
        }
        made = {}
        for rstatus in mapping:
            req = Request.objects.create(
                name=f"R-{rstatus}", event=self.event, status=rstatus,
                created_by=self.operator, registration_time=timezone.now(),
            )
            made[rstatus] = self._mk("draft", request=req)

        mod.backfill_status(apps, None)

        for rstatus, expected in mapping.items():
            made[rstatus].refresh_from_db()
            self.assertEqual(made[rstatus].status, expected, f"{rstatus} → {expected}")
