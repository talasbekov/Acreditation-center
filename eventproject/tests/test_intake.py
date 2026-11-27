"""Этап C — ввод, импорт и вложения: правило дублей, проверка файлов, идемпотентный импорт."""

import base64
import json
import os
import tempfile
import threading
import time
from datetime import date
from io import BytesIO, StringIO
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

import httpx
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, connection
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from directories.models import Country, DocumentType, Sex
from eventproject.models import Attendee, Event, Operator, PartnerReceipt, Request
from eventproject.services import intake
from eventproject.tests.media_fixtures import jpeg_bytes, valid_jpeg
from eventproject.views.integration import integrate_kazenergy as kazenergy

US = "1000000840"
KZ = "1000000105"


def _image_bytes(fmt, size=(600, 800)):
    buffer = BytesIO()
    Image.new("RGB", size, (90, 90, 90)).save(buffer, format=fmt)
    return buffer.getvalue()


class IntakeFixtures(TestCase):
    def setUp(self):
        cache.clear()  # django-ratelimit: 20 POST/ч на IP
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)

        Country.objects.get_or_create(country_code=US, defaults=dict(name_rus="США", name_kaz="АҚШ", name_eng="USA"))
        Country.objects.get_or_create(country_code=KZ, defaults=dict(name_rus="Казахстан", name_kaz="Қазақстан", name_eng="Kazakhstan"))
        Sex.objects.get_or_create(sex_code="M", defaults=dict(name_rus="М", name_kaz="Е", name_eng="M"))
        DocumentType.objects.get_or_create(doc_code="passport", defaults=dict(name_rus="Паспорт", name_kaz="Паспорт", name_eng="Passport"))

        self.event = Event.objects.create(name_rus="E", title="E", event_code="E1")
        self.user = User.objects.create_user("op", password="x")
        self.operator = Operator.objects.create(user=self.user, role="operator", patronymic="О", phone_number="+70000000001")
        self.operator.events.add(self.event)
        self.req = Request.objects.create(name="R", event=self.event, status="Active", created_by=self.operator,
                                          registration_time=timezone.now())

    def _existing(self, **over):
        data = dict(
            surname="Иванов", firstname="Иван", post="P", countryId=US, is_resident=False, docTypeId="passport",
            docSeries="AB", docNumber="123 456", docIssue="X", sexId="M", visitObjects="Зал",
            transcription="IVANOV IVAN", request=self.req, dateAdd=timezone.now(),
        )
        data.update(over)
        return Attendee.objects.create(**data)

    def _form(self, **over):
        cache.clear()
        data = {
            "csrfmiddlewaretoken": "known-token",
            "last_name": "Петров", "first_name": "Пётр", "patronymic": "", "latin_name": "PETROV PETR",
            "iin": "", "dob": "1990-01-01", "sex": "M", "citizenship": US, "post": "P",
            "document_type": "passport", "doc_series": "ab", "doc_number": "123-456",
            "doc_date_start": "2020-01-01", "doc_date_end": "2035-01-01", "doc_issuer": "X",
            "visit_objects": "Зал", "category": "", "photo": valid_jpeg("p.jpg"), "doc_photo": valid_jpeg("d.jpg"),
        }
        data.update(over)
        return data


class DuplicateRuleTests(IntakeFixtures):
    def test_same_document_is_duplicate_despite_formatting(self):
        self._existing()
        candidate = Attendee(countryId=US, docTypeId="passport", docSeries=" ab ", docNumber="123-456")
        self.assertEqual(intake.duplicate_of(candidate, self.event.pk), "document")

    def test_namesakes_with_different_documents_are_not_merged(self):
        self._existing()
        candidate = Attendee(countryId=US, docTypeId="passport", docSeries="AB", docNumber="999999",
                             surname="Иванов", firstname="Иван", transcription="IVANOV IVAN")
        self.assertIsNone(intake.duplicate_of(candidate, self.event.pk))

    def test_other_country_or_event_or_missing_number_is_not_duplicate(self):
        self._existing()
        self.assertIsNone(intake.duplicate_of(Attendee(countryId="1000000643", docTypeId="passport",
                                                       docSeries="AB", docNumber="123456"), self.event.pk))
        other = Event.objects.create(name_rus="O")
        self.assertIsNone(intake.duplicate_of(Attendee(countryId=US, docTypeId="passport", docSeries="AB",
                                                       docNumber="123456"), other.pk))
        self.assertIsNone(intake.duplicate_of(Attendee(countryId=US, docTypeId="passport", docSeries="AB",
                                                       docNumber=""), self.event.pk))

    def test_html_forms_reject_same_document_in_three_languages(self):
        self._existing()
        self.client.force_login(self.user)
        expected = {
            "": "Участник с этим документом уже добавлен",
            "/kz": "Осы құжатпен қатысушы",
            "/en": "An attendee with this document",
        }
        for prefix, text in expected.items():
            with self.subTest(prefix=prefix):
                response = self.client.post(f"{prefix}/add_attendee/{self.req.pk}/", self._form())
                self.assertContains(response, text)
        self.assertEqual(Attendee.objects.count(), 1)

    def test_html_form_accepts_namesake_with_other_document(self):
        self._existing()
        self.client.force_login(self.user)
        self.client.post(f"/add_attendee/{self.req.pk}/", self._form(
            last_name="Иванов", first_name="Иван", latin_name="IVANOV IVAN", doc_number="777777"))
        self.assertEqual(Attendee.objects.filter(surname="Иванов").count(), 2)

    def test_update_cannot_take_another_attendees_document(self):
        self._existing()
        mine = self._existing(surname="Сидоров", docNumber="555")
        self.client.force_login(self.user)
        data = self._form(last_name="Сидоров", doc_series="AB", doc_number="123456")
        data.pop("photo"), data.pop("doc_photo")
        response = self.client.post(f"/update_attendee/{mine.pk}/", data)
        self.assertContains(response, "Участник с этим документом уже добавлен")
        mine.refresh_from_db()
        self.assertEqual(mine.docNumber, "555")

    def test_api_rejects_non_resident_with_same_document(self):
        self._existing()
        client = APIClient()
        client.force_authenticate(self.user)
        payload = {
            "surname": "Петров", "firstname": "Пётр", "post": "P", "countryId": US, "docTypeId": "passport",
            "docSeries": "AB", "docNumber": "123456", "docIssue": "X", "sexId": "M", "visitObjects": "Зал",
            "transcription": "PETROV PETR", "request": self.req.pk, "birthDate": "1990-01-01",
        }
        response = client.post("/api/v1/attendees/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("docNumber", json.dumps(response.json(), ensure_ascii=False))
        payload["docNumber"] = "654321"
        self.assertEqual(client.post("/api/v1/attendees/", payload, format="json").status_code, 201)


class HtmlUploadTests(IntakeFixtures):
    def test_non_image_is_rejected_in_three_languages(self):
        self.client.force_login(self.user)
        fake = lambda: SimpleUploadedFile("p.jpg", b"<html>" + b"x" * 4096, content_type="image/jpeg")
        expected = {
            "": "Фото: файл не является изображением",
            "/kz": "Сурет: файл JPEG, PNG немесе WEBP суреті емес",
            "/en": "Photo: the file is not a JPEG, PNG or WEBP image",
        }
        for prefix, text in expected.items():
            with self.subTest(prefix=prefix):
                response = self.client.post(f"{prefix}/add_attendee/{self.req.pk}/", self._form(photo=fake()))
                self.assertContains(response, text)
        self.assertFalse(Attendee.objects.exists())
        self.assertEqual(list(Path(self.media.name).rglob("*.*")), [])

    def test_formats_outside_jpeg_png_webp_are_not_decoded(self):
        self.client.force_login(self.user)
        for fmt in ("GIF", "TIFF", "BMP"):
            with self.subTest(fmt=fmt):
                upload = SimpleUploadedFile(f"p.{fmt.lower()}", _image_bytes(fmt), content_type="image/jpeg")
                response = self.client.post(f"/add_attendee/{self.req.pk}/", self._form(photo=upload))
                self.assertContains(response, "Фото: файл не является изображением")
        self.assertFalse(Attendee.objects.exists())

    def test_landscape_scan_and_missing_file_get_clear_messages(self):
        self.client.force_login(self.user)
        wide = SimpleUploadedFile("d.jpg", jpeg_bytes(1200, 800), content_type="image/jpeg")
        self.assertContains(self.client.post(f"/en/add_attendee/{self.req.pk}/", self._form(doc_photo=wide)),
                            "Document scan: the image must be vertical")
        data = self._form()
        data.pop("photo")
        response = self.client.post(f"/add_attendee/{self.req.pk}/", data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Фото: файл не загружен")

    def test_valid_files_are_saved(self):
        self.client.force_login(self.user)
        self.client.post(f"/add_attendee/{self.req.pk}/", self._form())
        attendee = Attendee.objects.get()
        self.assertTrue(attendee.photo.name.startswith(f"event_{self.event.pk}/attendee_photos/"))
        self.assertTrue(attendee.docScan)

    def test_file_inputs_advertise_the_accepted_formats(self):
        # Браузерная проверка: подсказки и accept совпадают с правилами сервера (скан — с PDF).
        self.client.force_login(self.user)
        for prefix in ("", "/kz", "/en"):
            with self.subTest(prefix=prefix):
                html = self.client.get(f"{prefix}/add_attendee/{self.req.pk}/").content.decode()
                self.assertIn('accept=".jpg,.jpeg,.png,.webp"', html)
                self.assertIn('accept=".jpg,.jpeg,.png,.webp,.pdf"', html)
                self.assertIn("600×800", html)
                self.assertNotIn("7Mb", html)

    def test_update_form_keeps_files_optional_and_never_renders_none(self):
        # Браузерная проверка: пустое отчество показывалось как «None» и сохранялось строкой,
        # поля файлов были обязательными — любая правка требовала заново загрузить оба файла.
        attendee = self._existing(patronymic=None, docNumber="555",
                                  photo=ContentFile(jpeg_bytes(), name="p.jpg"),
                                  docScan=ContentFile(jpeg_bytes(), name="d.jpg"))
        self.client.force_login(self.user)
        html = self.client.get(f"/update_attendee/{attendee.pk}/").content.decode()
        self.assertNotIn('value="None"', html)
        self.assertNotRegex(html, r'<input type="file" required[^>]*name="(photo|doc_photo)"')
        data = self._form(last_name="Иванов", doc_number="555", post="Новая должность")
        data.pop("photo"), data.pop("doc_photo")
        self.client.post(f"/update_attendee/{attendee.pk}/", data)
        attendee.refresh_from_db()
        self.assertEqual(attendee.post, "Новая должность")
        self.assertFalse(attendee.patronymic)
        self.assertTrue(attendee.photo and attendee.docScan)

    def test_failed_insert_removes_already_stored_files(self):
        attendee = Attendee(
            surname="S", firstname="F", post="P", countryId=US, docTypeId="passport", docSeries="",
            docIssue="X", sexId="M", visitObjects="V", transcription="T", request=self.req,
            dateAdd=timezone.now(), status="bogus",
            photo=ContentFile(jpeg_bytes(), name="p.jpg"), docScan=ContentFile(jpeg_bytes(), name="d.jpg"),
        )
        with self.assertRaises(IntegrityError):
            intake.save_with_file_cleanup(attendee)
        self.assertEqual([p for p in Path(self.media.name).rglob("*") if p.is_file()], [])

    def test_failed_update_keeps_existing_files_and_drops_new_ones(self):
        # Этап E (матрица доступа): неудачная правка стирала прежние фото и скан участника.
        attendee = Attendee.objects.create(
            surname="S", firstname="F", post="P", countryId=US, docTypeId="passport", docSeries="",
            docIssue="X", sexId="M", visitObjects="V", transcription="T", request=self.req,
            dateAdd=timezone.now(), photo=ContentFile(jpeg_bytes(), name="p.jpg"),
            docScan=ContentFile(jpeg_bytes(), name="d.jpg"),
        )
        old_photo, old_scan = attendee.photo.name, attendee.docScan.name
        attendee.photo = ContentFile(jpeg_bytes(), name="new.jpg")
        attendee.photo.save("new.jpg", attendee.photo, save=False)
        new_photo = attendee.photo.name
        attendee.birthDate = ""  # неверная дата → запись не удаётся
        with self.assertRaises(Exception):
            intake.save_with_file_cleanup(attendee)
        stored = {p.relative_to(self.media.name).as_posix() for p in Path(self.media.name).rglob("*") if p.is_file()}
        self.assertIn(old_photo, stored)
        self.assertIn(old_scan, stored)
        self.assertNotIn(new_photo, stored)


def _record(rid, **over):
    data = {
        "id": rid, "surname": "Иванов", "firstname": "Иван", "post": "P", "countryId": US,
        "docTypeId": "passport", "docSeries": "AB", "docNumber": f"N{rid}", "sexId": "M",
        "visitObjects": "Зал", "transcription": "IVANOV IVAN", "dateAdd": "2026-11-25T10:00:00Z",
        "birthDate": "1990-01-01", "docBegin": "2020-01-01", "docEnd": "2035-01-01", "iin": "990101300123",
    }
    data.update(over)
    return data


class PartnerImportTests(IntakeFixtures):
    def _run(self, queue, ack_status=200):
        """``queue`` — список ответов GET (списки анкет); ACK отвечает ``ack_status``."""
        gets = iter(queue)
        acks = []

        def transport(request):
            if request.method == "GET":
                return httpx.Response(200, json={"attendees": next(gets, [])})
            acks.append(json.loads(request.content))
            status = ack_status(len(acks)) if callable(ack_status) else ack_status
            return httpx.Response(status)

        client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        with patch.object(kazenergy, "API_KEY", "fixture"), patch.object(kazenergy.httpx, "AsyncClient", return_value=client):
            response = async_to_sync(kazenergy.kazenergy_receive)(RequestFactory().get("/"), self.event.pk, self.operator.pk)
        return response, acks

    def test_resent_record_creates_one_attendee_and_repeats_the_same_ack(self):
        # Первый ACK не дошёл → импорт останавливается; партнёр присылает ту же анкету снова.
        _, first = self._run([[_record(7)], [_record(8)]], ack_status=503)
        self.assertEqual(len(first), 1)
        self.assertEqual(Attendee.objects.filter(docNumber="N7").count(), 1)
        self.assertFalse(Attendee.objects.filter(docNumber="N8").exists())

        response, second = self._run([[_record(7)], []])
        self.assertEqual(second, first)
        self.assertEqual(Attendee.objects.filter(docNumber="N7").count(), 1)
        receipt = PartnerReceipt.objects.get(external_id="7")
        self.assertEqual((receipt.ack_attempts, receipt.last_ack_status), (2, 200))
        self.assertIsNotNone(receipt.acked_at)
        self.assertEqual(response.status_code, 200)

    def test_partner_repeating_an_acknowledged_record_does_not_loop(self):
        response, acks = self._run([[_record(1)]] * 50)
        self.assertEqual(len(acks), 1)
        self.assertEqual(Attendee.objects.count(), 1)
        self.assertEqual(json.loads(response.content)["processed"], 2)

    def test_namesakes_are_both_imported_and_same_document_is_duplicate(self):
        response, acks = self._run([[_record(1)], [_record(2)], [_record(3, docNumber="N1", surname="Другой")], []])
        self.assertEqual(Attendee.objects.filter(transcription="IVANOV IVAN").count(), 2)
        self.assertEqual([a["code"] for a in acks], [2, 2, 2])
        self.assertEqual(PartnerReceipt.objects.get(external_id="3").outcome, PartnerReceipt.DUPLICATE)
        self.assertEqual(json.loads(response.content)["duplicates"], 1)

    def test_bad_photo_is_dropped_record_accepted_with_note(self):
        good = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes()).decode()
        bad = base64.b64encode(b"not an image" * 100).decode()
        _, acks = self._run([[_record(5, photo=bad, docScan=good)], []])
        attendee = Attendee.objects.get()
        self.assertFalse(attendee.photo)
        self.assertTrue(attendee.docScan.name.endswith(".jpg"))
        # Имя случайное, без идентификатора партнёра (раньше было «5_docScan.jpg»).
        self.assertRegex(Path(attendee.docScan.name).name, r"^[0-9a-f]{32}_docScan\.jpg$")
        self.assertEqual(acks[0]["code"], 2)
        self.assertIn("Фото не принято", acks[0]["message"])
        self.assertEqual(attendee.status, "draft")

    def test_oversized_file_is_refused_before_decoding(self):
        huge = "A" * (8 * 1024 * 1024)
        with patch("base64.b64decode") as decode:
            _, acks = self._run([[_record(6, photo=huge)], []])
            decode.assert_not_called()
        self.assertIn("слишком большой", acks[0]["message"])

    def test_missing_fields_and_bad_dates_are_rejected_without_attendee(self):
        response, acks = self._run([[{"id": 1, "surname": "X"}], [_record(2, birthDate="1990-13-45")], []])
        self.assertEqual([a["code"] for a in acks], [9, 9])
        self.assertIn("birthDate", acks[1]["message"])
        self.assertFalse(Attendee.objects.exists())
        self.assertEqual(response.status_code, 400)

    def test_record_without_id_stops_import(self):
        response, acks = self._run([[_record(None)], [_record(2)]])
        self.assertEqual(acks, [])
        self.assertFalse(Attendee.objects.exists())
        self.assertEqual(response.status_code, 400)

    def test_sent_request_is_not_extended_and_non_resident_keeps_no_iin(self):
        Request.objects.filter(pk=self.req.pk).update(status="Sent")
        self._run([[_record(1)], []])
        attendee = Attendee.objects.get()
        self.assertNotEqual(attendee.request_id, self.req.pk)
        self.assertEqual(attendee.request.status, "Active")
        self.assertEqual((attendee.is_resident, attendee.iin), (False, None))

    def test_empty_queue_creates_no_request(self):
        before = Request.objects.count()
        self._run([[]])
        self.assertEqual(Request.objects.count(), before)

    @override_settings(PARTNER_IMPORT_MAX_RECORDS=3)
    def test_run_is_bounded(self):
        _, acks = self._run([[_record(i)] for i in range(1, 10)])
        self.assertEqual(len(acks), 3)


class OrphanMediaCommandTests(IntakeFixtures):
    def test_counts_and_deletes_only_old_unreferenced_files(self):
        self.client.force_login(self.user)
        self.client.post(f"/add_attendee/{self.req.pk}/", self._form())
        folder = Path(self.media.name) / f"event_{self.event.pk}" / "attendee_photos"
        orphan, fresh = folder / "orphan.jpg", folder / "fresh.jpg"
        orphan.write_bytes(b"x")
        fresh.write_bytes(b"y")
        old = time.time() - 3 * 3600
        os.utime(orphan, (old, old))

        out = StringIO()
        call_command("find_orphan_media", stdout=out)
        self.assertIn("Найдено файлов без записи: 1", out.getvalue())
        self.assertNotIn("orphan", out.getvalue())
        self.assertTrue(orphan.exists())

        call_command("find_orphan_media", "--delete", stdout=StringIO())
        self.assertFalse(orphan.exists())
        self.assertTrue(fresh.exists())
        attendee = Attendee.objects.get()
        self.assertTrue(Path(attendee.photo.path).exists())
        self.assertTrue(Path(attendee.docScan.path).exists())


@skipUnless(connection.vendor == "postgresql", "блокировка строк проверяется на PostgreSQL")
class ConcurrentIntakeTests(TransactionTestCase):
    def test_two_simultaneous_saves_of_one_document_create_one_attendee(self):
        event = Event.objects.create(name_rus="E")
        user = User.objects.create_user("op2")
        operator = Operator.objects.create(user=user, patronymic="О", phone_number="+7")
        req = Request.objects.create(name="R", event=event, status="Active", created_by=operator,
                                     registration_time=timezone.now())
        barrier = threading.Barrier(2)
        results = []

        def worker(n):
            from django.db import connection as thread_connection
            try:
                attendee = Attendee(
                    surname=f"S{n}", firstname="F", post="P", countryId=US, docTypeId="passport",
                    docSeries="AB", docNumber="RACE1", docIssue="X", sexId="M", visitObjects="V",
                    transcription="T", request=req, dateAdd=timezone.now(), is_resident=False,
                )
                barrier.wait()
                results.append(intake.save_unless_duplicate(attendee, event.pk))
            finally:
                thread_connection.close()

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results, key=str), sorted([None, "document"], key=str))
        self.assertEqual(Attendee.objects.filter(docNumber="RACE1").count(), 1)
