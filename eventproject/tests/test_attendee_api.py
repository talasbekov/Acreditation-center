"""Story 3.4 — тесты DRF AttendeeViewSet (AC-7).

Story 5.3 — multipart-загрузка фото/документа (AttendeeUploadTests).
"""

import shutil
import tempfile
from datetime import date
from io import BytesIO
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from directories.models import Country
from eventproject.models import Attendee, Category, Event, Operator, Request
from eventproject.serializers.attendee import _strip_blank_file_fields
from eventproject.views.attendee_api import AttendeeViewSet


class StripBlankFileFieldsTests(SimpleTestCase):
    """P1-6 — снятие пустых файловых полей сохраняет multi-value QueryDict."""

    def test_preserves_multivalue_and_drops_blank_file(self):
        qd = QueryDict(mutable=True)
        qd.setlist("visitObjects", ["Зал A", "Зал B"])
        qd["photo"] = ""
        qd["surname"] = "Иванов"
        result = _strip_blank_file_fields(qd, ["photo"])
        # QueryDict-ность (и html-input маркер) сохранены, multi-value не усечён.
        self.assertIsInstance(result, QueryDict)
        self.assertEqual(result.getlist("visitObjects"), ["Зал A", "Зал B"])
        self.assertNotIn("photo", result)
        self.assertEqual(result.get("surname"), "Иванов")

    def test_plain_dict_drops_blank_file(self):
        result = _strip_blank_file_fields(
            {"photo": "", "surname": "Иванов"}, ["photo"]
        )
        self.assertEqual(result, {"surname": "Иванов"})

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
        # BE-5: countryId сверяется со справочником Country.country_code. KZ не
        # требует строки (is_resident_country коротит), а легитимный нерезидент
        # OTHER должен существовать как реальная страна.
        Country.objects.create(
            country_code=OTHER, name_rus="Иномания", name_kaz="Ino", name_eng="Ino",
            country_iso="IN",
        )
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

    def test_create_malformed_country_id_rejected_not_silent_iin_drop(self):
        # BE-5: countryId, похожий на КЗ, но малформ ("1000000105aaaa"), нельзя
        # молча трактовать как нерезидента и отбрасывать ИИН — это неизвестный
        # код страны (нет в справочнике Country.country_code).
        before = Attendee.objects.count()
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(countryId="1000000105aaaa"),
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["field"], "countryId")
        self.assertEqual(Attendee.objects.count(), before)

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


class AttendeeReviewPatchTests(AttendeeApiBase):
    """Story 3.4 — фиксы код-ревью (2026-06-23)."""

    def test_update_cannot_move_to_foreign_event(self):
        # Critical: writable `request` без RBAC-проверки на update позволял увести
        # участника в чужое мероприятие. Теперь validate() это блокирует (403).
        resp = self.client.patch(
            f"/api/v1/attendees/{self.attendee1.id}/",
            {"request": self.request2.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.attendee1.refresh_from_db()
        self.assertEqual(self.attendee1.request_id, self.request1.id)

    def test_create_foreign_event_is_403_before_dedup(self):
        # Info-leak: attendee2 уже имеет VALID_IIN в event2 (чужом). Без фикса
        # дедуп сработал бы первым (400 «уже добавлен» = утечка). RBAC раньше
        # дедупа → 403, факт существования ИИН не раскрывается.
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(
                request=self.request2.id, iin=VALID_IIN, birthDate="1985-12-05"
            ),
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    @patch("eventproject.views.attendee_api.audit_log")
    def test_update_emits_audit(self, mock_audit):
        resp = self.client.patch(
            f"/api/v1/attendees/{self.attendee1.id}/",
            {"post": "Обновлён"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        actions = [c.kwargs.get("action") for c in mock_audit.call_args_list]
        self.assertIn("attendee.update", actions)

    @patch("eventproject.views.attendee_api.audit_log")
    def test_delete_emits_audit(self, mock_audit):
        resp = self.client.delete(f"/api/v1/attendees/{self.attendee1.id}/")
        self.assertEqual(resp.status_code, 204)
        actions = [c.kwargs.get("action") for c in mock_audit.call_args_list]
        self.assertIn("attendee.delete", actions)


class AttendeeUploadTests(AttendeeApiBase):
    """Story 5.3 — multipart фото/документ: Pillow-валидация, PDF→JPEG, two-phase,
    post_delete cleanup. Каждый тест получает изолированный MEDIA_ROOT (tmp)."""

    def setUp(self):
        super().setUp()
        tmp_media = tempfile.mkdtemp(prefix="s53_media_")
        override = override_settings(MEDIA_ROOT=tmp_media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(lambda: shutil.rmtree(tmp_media, ignore_errors=True))

    def _img_upload(self, w, h, name="photo.jpg"):
        buf = BytesIO()
        Image.new("RGB", (w, h), (100, 120, 140)).save(buf, format="JPEG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")

    def _pdf_upload(self, w=600, h=800, name="doc.pdf"):
        buf = BytesIO()
        Image.new("RGB", (w, h), (210, 210, 210)).save(buf, format="PDF")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="application/pdf")

    # ── AC-3: серверная Pillow-валидация фото ────────────────────────────
    def test_create_with_valid_photo(self):
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(photo=self._img_upload(600, 800)),
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        attendee = Attendee.objects.get(id=resp.data["id"])
        self.assertTrue(attendee.photo)
        self.assertTrue(attendee.photo.storage.exists(attendee.photo.name))

    def test_oversize_photo_rejected(self):
        big = SimpleUploadedFile(
            "big.jpg", b"\x00" * (5 * 1024 * 1024 + 1), content_type="image/jpeg"
        )
        resp = self.client.post(
            "/api/v1/attendees/", self._payload(photo=big), format="multipart"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["field"], "photo")

    def test_horizontal_photo_rejected(self):
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(photo=self._img_upload(800, 600)),
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["field"], "photo")

    def test_low_res_photo_rejected(self):
        # 400×500 — ratio 0.8 OK, но разрешение < 600×800.
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(photo=self._img_upload(400, 500)),
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["field"], "photo")

    # ── AC-4: PDF документа → JPEG, далее как фото ────────────────────────
    def test_pdf_docscan_converted_to_jpeg(self):
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(docScan=self._pdf_upload(600, 800)),
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        attendee = Attendee.objects.get(id=resp.data["id"])
        self.assertTrue(attendee.docScan.name.endswith(".jpg"))
        self.assertTrue(attendee.docScan.storage.exists(attendee.docScan.name))

    def test_image_docscan_accepted(self):
        # docScan принимает и обычное изображение (вертикальное 3×4).
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(docScan=self._img_upload(600, 800, name="scan.jpg")),
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)

    # ── AC-5: post_delete Signal удаляет файлы (transaction.on_commit) ────
    def test_post_delete_removes_files(self):
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(photo=self._img_upload(600, 800)),
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        attendee = Attendee.objects.get(id=resp.data["id"])
        name, storage = attendee.photo.name, attendee.photo.storage
        self.assertTrue(storage.exists(name))
        # post_delete отложен до commit → исполняем on_commit-колбэки в тесте.
        with self.captureOnCommitCallbacks(execute=True):
            attendee.delete()
        self.assertFalse(storage.exists(name))

    # ── code-review patch: PDF >5МБ отклоняется ДО конвертации (по исходнику) ─
    def test_oversize_pdf_docscan_rejected_before_conversion(self):
        pdf = self._pdf_upload(600, 800).read()
        big = SimpleUploadedFile(
            "big.pdf", pdf + b"\x00" * (5 * 1024 * 1024), content_type="application/pdf"
        )
        resp = self.client.post(
            "/api/v1/attendees/", self._payload(docScan=big), format="multipart"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["field"], "docScan")

    # ── code-review patch: пустая строка файла → «без файла», не англ.ошибка ─
    def test_empty_string_photo_treated_as_no_file(self):
        resp = self.client.post(
            "/api/v1/attendees/", self._payload(photo=""), format="multipart"
        )
        self.assertEqual(resp.status_code, 201, resp.content)

    # ── Регрессия: JSON-поток (5.2) не сломан ────────────────────────────
    def test_json_flow_without_files_still_works(self):
        resp = self.client.post(
            "/api/v1/attendees/", self._payload(), format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.content)


class AttendeeMediaReplaceCleanupTests(AttendeeApiBase):
    """Story 5.5 (code-review patch) — замена photo/docScan в edit-PATCH удаляет
    СТАРЫЙ файл (pre_save Signal), иначе копились бы orphaned PII-медиа.
    Story 5.3 отложила это до edit-UI; здесь закрыто. Изолированный MEDIA_ROOT."""

    def setUp(self):
        super().setUp()
        tmp_media = tempfile.mkdtemp(prefix="s55_media_")
        override = override_settings(MEDIA_ROOT=tmp_media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(lambda: shutil.rmtree(tmp_media, ignore_errors=True))

    def _img_upload(self, w, h, name="photo.jpg"):
        buf = BytesIO()
        Image.new("RGB", (w, h), (100, 120, 140)).save(buf, format="JPEG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")

    def test_replacing_photo_deletes_old_file(self):
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(photo=self._img_upload(600, 800, name="old.jpg")),
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        attendee = Attendee.objects.get(id=resp.data["id"])
        old_name, storage = attendee.photo.name, attendee.photo.storage
        self.assertTrue(storage.exists(old_name))

        # PATCH с новым фото → старый файл удаляется на commit; новый остаётся.
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(
                f"/api/v1/attendees/{attendee.id}/",
                {"photo": self._img_upload(600, 800, name="new.jpg")},
                format="multipart",
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        attendee.refresh_from_db()
        self.assertNotEqual(attendee.photo.name, old_name)
        self.assertFalse(storage.exists(old_name))  # старый удалён
        self.assertTrue(storage.exists(attendee.photo.name))  # новый на месте

    def test_create_does_not_trigger_replace_cleanup(self):
        # Регрессия: на create (нет старого файла) pre_save не падает и файл цел.
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(photo=self._img_upload(600, 800)),
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        attendee = Attendee.objects.get(id=resp.data["id"])
        self.assertTrue(attendee.photo.storage.exists(attendee.photo.name))

    def test_patch_without_file_keeps_existing(self):
        # PATCH без файлового поля не трогает уже загруженное фото.
        resp = self.client.post(
            "/api/v1/attendees/",
            self._payload(photo=self._img_upload(600, 800, name="keep.jpg")),
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        attendee = Attendee.objects.get(id=resp.data["id"])
        name, storage = attendee.photo.name, attendee.photo.storage
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(
                f"/api/v1/attendees/{attendee.id}/", {"post": "Изм"}, format="multipart"
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(storage.exists(name))  # фото на месте — не удалено


class AttendeeSearchListTests(AttendeeApiBase):
    """Story 5.5 — поиск по имени (`?search=`) + masked-list-serializer."""

    def test_search_by_surname_matches(self):
        resp = self.client.get("/api/v1/attendees/", {"search": "Существующий"})
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertIn(self.attendee1.id, ids)

    def test_search_excludes_non_match(self):
        resp = self.client.get("/api/v1/attendees/", {"search": "Несуществующий"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)

    def test_search_rbac_isolation(self):
        # attendee2 (surname «Чужой») в чужом мероприятии — поиск его не видит.
        resp = self.client.get("/api/v1/attendees/", {"search": "Чужой"})
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertNotIn(self.attendee2.id, ids)

    def test_search_rbac_isolation_same_surname_cross_tenant(self):
        # P2-3: однофамилец в ЧУЖОМ событии не должен попадать в результаты — изоляция
        # держится get_queryset, а не уникальностью фамилии (adversarial кросс-tenant).
        twin = _make_attendee(self.request2, surname=self.attendee1.surname)
        resp = self.client.get(
            "/api/v1/attendees/", {"search": self.attendee1.surname}
        )
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertIn(self.attendee1.id, ids)   # свой — виден
        self.assertNotIn(twin.id, ids)          # чужой однофамилец — отсечён RBAC

    @skipUnless(
        connection.vendor == "postgresql",
        "Кейс-фолдинг кириллицы в icontains работает только на Postgres (prod); "
        "SQLite LIKE — ASCII-only. Тест документирует/защищает прод-поведение.",
    )
    def test_search_cyrillic_case_insensitive(self):
        # P2-4: на Postgres ILIKE кейс-фолдит кириллицу → поиск в нижнем регистре
        # находит запись с заглавной. Расхождение test(SQLite)/prod(PG) явно отмечено.
        resp = self.client.get(
            "/api/v1/attendees/", {"search": self.attendee1.surname.lower()}
        )
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in resp.data["results"]]
        self.assertIn(self.attendee1.id, ids)

    def test_list_masks_iin_no_raw(self):
        resp = self.client.get("/api/v1/attendees/")
        self.assertEqual(resp.status_code, 200)
        row = next(r for r in resp.data["results"] if r["id"] == self.attendee1.id)
        self.assertIn("iin_masked", row)
        self.assertNotIn("iin", row)
        self.assertTrue(row["iin_masked"].startswith("********"))
        self.assertTrue(row["iin_masked"].endswith(VALID_IIN[-4:]))

    def test_detail_has_full_iin(self):
        resp = self.client.get(f"/api/v1/attendees/{self.attendee1.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["iin"], VALID_IIN)


class AttendeeEditAtomicityTests(AttendeeApiBase):
    """P1-5/P1-10 — атомарность edit-путей и аудит отброса ИИН."""

    def test_partial_update_rolls_back_on_audit_failure(self):
        # P1-5: сбой аудита после save не должен оставлять сохранённую правку без
        # аудит-строки — save+audit атомарны (паритет с perform_create).
        url = f"/api/v1/attendees/{self.attendee1.id}/"
        original = self.attendee1.surname
        with patch.object(
            AttendeeViewSet, "_audit_write", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                self.client.patch(url, {"surname": "Новая"}, format="json")
        self.attendee1.refresh_from_db()
        self.assertEqual(self.attendee1.surname, original)  # откат правки

    def test_update_rolls_back_on_audit_failure(self):
        # P1-5: тот же инвариант для PUT (полное обновление).
        url = f"/api/v1/attendees/{self.attendee1.id}/"
        original = self.attendee1.surname
        with patch.object(
            AttendeeViewSet, "_audit_write", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                self.client.put(url, self._payload(surname="Полная"), format="json")
        self.attendee1.refresh_from_db()
        self.assertEqual(self.attendee1.surname, original)

    def test_destroy_rolls_back_on_audit_failure(self):
        # P1-5: сбой аудита после delete не должен оставлять удаление без аудит-строки.
        url = f"/api/v1/attendees/{self.attendee1.id}/"
        with patch.object(
            AttendeeViewSet, "_audit_write", side_effect=RuntimeError("audit down")
        ):
            with self.assertRaises(RuntimeError):
                self.client.delete(url)
        self.assertTrue(Attendee.objects.filter(id=self.attendee1.id).exists())

    def test_iin_discard_on_residency_change_is_audited(self):
        # P1-10: при РК→не-РК ранее сохранённый ИИН отбрасывается — это должно
        # попасть в аудит (с маскированным ИИН), а не исчезнуть молча.
        url = f"/api/v1/attendees/{self.attendee1.id}/"
        with patch("eventproject.views.attendee_api.audit_log") as mock_audit:
            resp = self.client.patch(
                url, {"countryId": OTHER, "iin": ""}, format="json"
            )
        self.assertEqual(resp.status_code, 200)
        self.attendee1.refresh_from_db()
        self.assertIsNone(self.attendee1.iin)
        discard_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get("action") == "attendee.iin_discarded"
        ]
        self.assertEqual(len(discard_calls), 1)
        # Маскированный ИИН (последние 4), не plaintext.
        self.assertEqual(discard_calls[0].kwargs["extra"]["iin"][-4:], VALID_IIN[-4:])
        self.assertNotIn(VALID_IIN, str(discard_calls[0].kwargs["extra"]))

    def test_no_iin_discard_audit_when_iin_unchanged(self):
        # P1-10: обычная правка (без отброса ИИН) не плодит лишних discard-записей.
        url = f"/api/v1/attendees/{self.attendee1.id}/"
        with patch("eventproject.views.attendee_api.audit_log") as mock_audit:
            resp = self.client.patch(url, {"surname": "Петров"}, format="json")
        self.assertEqual(resp.status_code, 200)
        actions = [c.kwargs.get("action") for c in mock_audit.call_args_list]
        self.assertNotIn("attendee.iin_discarded", actions)
