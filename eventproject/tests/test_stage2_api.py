"""Второй этап: доп. поля, результат СГО, бейджи, саморегистрация, API-токены, журнал."""

import io
import json
import shutil
import tempfile
import uuid
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from directories.models import Country
from eventproject.models import (
    ApiToken, Attendee, CustomField, Event, ExportLog, Job, Operator, RegistrationLink, Request,
)

MEDIA = tempfile.mkdtemp()
PRIVATE = tempfile.mkdtemp()


def _jpeg(name="p.jpg", size=(600, 800)):
    buf = io.BytesIO()
    Image.new("RGB", size, "#336699").save(buf, "JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def _attendee(req, n, **kw):
    data = dict(
        surname=f"Фам{n}", firstname="Имя", birthDate=date(1990, 1, 1), post="x", countryId="1000000224",
        docTypeId="1000000002", docNumber=f"D{n}", docBegin=date(2020, 1, 1), docEnd=date(2030, 1, 1),
        sexId="1000000001", visitObjects="x", transcription="FAM IMYA", request=req, dateAdd=timezone.now(), status="exported",
    )
    data.update(kw)
    return Attendee.objects.create(**data)


def _form(req_id=None, n=1, **extra):
    data = {
        "surname": "Ким", "firstname": "Ли", "birthDate": "1990-01-01", "post": "Инженер", "countryId": "1000000224",
        "docTypeId": "1000000002", "docNumber": f"Z{n}", "docBegin": "2020-01-01", "docEnd": "2030-01-01",
        "sexId": "1000000001", "visitObjects": "Зал", "transcription": "KIM LI", "stickId": "1100000005",
    }
    if req_id is not None:
        data["request"] = req_id
    data.update(extra)
    return data


@override_settings(MEDIA_ROOT=MEDIA, PRIVATE_FILES_ROOT=PRIVATE, JOBS_RUN_INLINE=True)
class Stage2Base(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)
        shutil.rmtree(PRIVATE, ignore_errors=True)

    def setUp(self):
        cache.clear()
        Country.objects.create(country_code="1000000224", name_rus="США", name_kaz="АҚШ", name_eng="USA")
        Country.objects.create(country_code="1000000105", name_rus="Казахстан", name_kaz="Қазақстан", name_eng="Kazakhstan")
        today = date.today()
        self.event = Event.objects.create(
            name_rus="Форум", name_kaz="Форум", name_eng="Forum", event_code="F",
            date_start=today + timedelta(days=3), date_end=today + timedelta(days=5),
        )
        self.op_user = User.objects.create_user("op", password="Strong-pass-123")
        self.op = Operator.objects.create(user=self.op_user, role="operator", patronymic="x")
        self.op.events.add(self.event)
        self.sup_user = User.objects.create_user("sup", password="Strong-pass-123")
        Operator.objects.create(user=self.sup_user, role="superoperator", patronymic="x")
        self.admin = User.objects.create_superuser("su", "su@example.com", "Strong-pass-123")
        self.req = Request.objects.create(
            name="R", event=self.event, status="Active", created_by=self.op, registration_time=timezone.now()
        )
        self.op_client = APIClient()
        self.op_client.force_authenticate(self.op_user)
        self.sup = APIClient()
        self.sup.force_authenticate(self.sup_user)


class CustomFieldTests(Stage2Base):
    def test_crud_and_required_on_create(self):
        url = f"/api/v1/events/{self.event.id}/custom-fields/"
        made = self.op_client.post(url, {"field_name": "Парковка", "is_required": True}, format="json")
        self.assertEqual(made.status_code, 201, made.content)
        fid = made.json()["id"]
        self.assertEqual(self.op_client.post(url, {"field_name": "Парковка"}, format="json").json()["type"], "custom_field_name_taken")
        sel = self.op_client.post(url, {"field_name": "Цвет", "field_type": "select"}, format="json")
        self.assertEqual(sel.json()["type"], "custom_field_options_required")

        no_value = self.op_client.post("/api/v1/attendees/", _form(self.req.id), format="json")
        self.assertEqual(no_value.status_code, 400)
        self.assertEqual(no_value.json()["type"], "custom_field_required")
        ok = self.op_client.post(
            "/api/v1/attendees/", _form(self.req.id, custom_field_values={str(fid): "A-42"}), format="json"
        )
        self.assertEqual(ok.status_code, 201, ok.content)
        self.assertEqual(Attendee.objects.get(pk=ok.json()["id"]).custom_field_values, {str(fid): "A-42"})

        self.assertEqual(self.op_client.put(f"/api/v1/custom-fields/{fid}/", {"field_name": "Место"}, format="json").status_code, 200)
        self.assertEqual(self.op_client.delete(f"/api/v1/custom-fields/{fid}/").status_code, 204)
        self.assertFalse(CustomField.objects.exists())

    def test_limit_twenty(self):
        for i in range(CustomField.MAX_PER_EVENT):
            CustomField.objects.create(event=self.event, field_name=f"f{i}")
        resp = self.op_client.post(f"/api/v1/events/{self.event.id}/custom-fields/", {"field_name": "x"}, format="json")
        self.assertEqual(resp.json()["type"], "custom_field_limit")


class SgoResultTests(Stage2Base):
    def setUp(self):
        super().setUp()
        self.a1, self.a2 = _attendee(self.req, 1), _attendee(self.req, 2)
        self.pkg = ExportLog.objects.create(
            event=self.event, category=self.req, exported_before=timezone.now(), user=self.sup_user,
            attendee_count=2, package_id=uuid.uuid4(), attendee_ids=[self.a1.pk, self.a2.pk], manifest={},
        )

    def url(self):
        return f"/api/v1/staff/packages/{self.pkg.package_id}/execute/"

    def test_execute_sets_access(self):
        body = {"export_id": str(self.pkg.package_id), "event_id": self.event.id, "denied_participant_ids": [self.a2.pk]}
        resp = self.sup.post(self.url(), body, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual((resp.json()["allowed"], resp.json()["denied"]), (1, 1))
        self.a1.refresh_from_db()
        self.a2.refresh_from_db()
        self.assertEqual((self.a1.access_status, self.a2.access_status), ("yes", "no"))
        # повторное исполнение перезаписывает решения
        again = self.sup.post(self.url(), {"denied_participant_ids": []}, format="json")
        self.assertEqual(again.json()["allowed"], 2)
        self.a2.refresh_from_db()
        self.assertEqual(self.a2.access_status, "yes")

    def test_file_upload_and_errors(self):
        file = SimpleUploadedFile("r.json", json.dumps({"denied_participant_ids": [self.a1.pk]}).encode(), "application/json")
        self.assertEqual(self.sup.post(self.url(), {"result": file}, format="multipart").status_code, 200)
        unknown = self.sup.post(self.url(), {"denied_participant_ids": [999999]}, format="json")
        self.assertEqual(unknown.json()["type"], "sgo_result_unknown_ids")
        wrong = self.sup.post(self.url(), {"export_id": str(uuid.uuid4()), "denied_participant_ids": []}, format="json")
        self.assertEqual(wrong.json()["type"], "sgo_result_wrong_package")
        self.assertEqual(self.op_client.post(self.url(), {}, format="json").status_code, 403)


class BadgeTests(Stage2Base):
    def setUp(self):
        super().setUp()
        self.yes = _attendee(self.req, 1, access_status="yes", photo=_jpeg())
        self.no = _attendee(self.req, 2, access_status="no")

    def test_template_defaults_and_preview(self):
        t = self.sup.get(f"/api/v1/events/{self.event.id}/badge-template/").json()
        self.assertTrue(t["is_default"])
        self.assertEqual(t["layout"]["badge"]["dpi"], 300)
        png = self.sup.get(f"/api/v1/events/{self.event.id}/badges/preview/?attendee={self.yes.pk}")
        self.assertEqual(png["Content-Type"], "image/png")
        bad = self.sup.post(
            f"/api/v1/events/{self.event.id}/badges/preview/", {"layout": {"photo": {"x_mm": 500}}}, format="json"
        )
        self.assertEqual(bad.json()["type"], "badge_layout_invalid")

    def test_background_must_match_card(self):
        wrong = self.sup.put(
            f"/api/v1/events/{self.event.id}/badge-template/", {"background": _jpeg("bg.jpg", (1200, 1200))}, format="multipart"
        )
        self.assertEqual(wrong.json()["type"], "badge_background_invalid")
        ok = self.sup.put(
            f"/api/v1/events/{self.event.id}/badge-template/",
            {"background": _jpeg("bg.jpg", (1011, 638)), "name_source": "latin"},
            format="multipart",
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertTrue(ok.json()["has_background"])

    def test_single_badge(self):
        refused = self.sup.get(f"/api/v1/events/{self.event.id}/attendees/{self.no.pk}/badge.pdf")
        self.assertEqual(refused.json()["type"], "badge_not_allowed")
        pdf = self.sup.get(f"/api/v1/events/{self.event.id}/attendees/{self.yes.pk}/badge.pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.yes.refresh_from_db()
        self.assertIsNotNone(self.yes.badge_printed_at)

    def test_batch_job(self):
        refused = self.sup.post(f"/api/v1/events/{self.event.id}/badges/", {"attendee_ids": [self.yes.pk, self.no.pk]}, format="json")
        self.assertEqual(refused.json()["type"], "badge_not_allowed")
        with self.captureOnCommitCallbacks(execute=True):
            made = self.sup.post(f"/api/v1/events/{self.event.id}/badges/", {}, format="json")
        self.assertEqual(made.status_code, 202, made.content)
        job = self.sup.get(f"/api/v1/jobs/{made.json()['id']}/").json()
        self.assertEqual(job["status"], "completed", job)
        self.assertEqual(job["result"]["badge_count"], 1)
        file = self.sup.get(f"/api/v1/jobs/{job['id']}/file/")
        self.assertTrue(b"".join(file.streaming_content).startswith(b"%PDF"))
        self.yes.refresh_from_db()
        self.assertIsNotNone(self.yes.badge_printed_at)
        nothing = self.sup.post(f"/api/v1/events/{self.event.id}/badges/", {}, format="json")
        self.assertEqual(nothing.json()["type"], "badge_nothing_to_print")
        self.assertEqual(self.op_client.get(f"/api/v1/jobs/{job['id']}/").status_code, 403)

    def test_worker_command(self):
        from django.core.management import call_command

        with self.settings(JOBS_RUN_INLINE=False):
            made = self.sup.post(f"/api/v1/events/{self.event.id}/badges/", {"attendee_ids": [self.yes.pk]}, format="json")
        self.assertEqual(Job.objects.get(pk=made.json()["id"]).status, "pending")
        call_command("run_jobs", "--once", stdout=io.StringIO())
        self.assertEqual(Job.objects.get(pk=made.json()["id"]).status, "completed")


class RegistrationLinkTests(Stage2Base):
    def test_single_link_flow(self):
        made = self.op_client.post(
            f"/api/v1/events/{self.event.id}/registration-links/", {"link_type": "single", "count": 2}, format="json"
        )
        self.assertEqual(made.status_code, 201, made.content)
        token = made.json()["results"][0]["token"]
        link = RegistrationLink.objects.get(token=token)
        self.assertEqual(link.request.source, "self_registration")
        public = APIClient()
        info = public.get(f"/api/v1/public/register/{token}/")
        self.assertEqual(info.status_code, 200)
        self.assertIn("countries", info.json()["directories"])
        no_files = public.post(f"/api/v1/public/register/{token}/", _form(), format="multipart")
        self.assertEqual(no_files.status_code, 400)
        ok = public.post(f"/api/v1/public/register/{token}/", _form(photo=_jpeg(), docScan=_jpeg("d.jpg")), format="multipart")
        self.assertEqual(ok.status_code, 201, ok.content)
        a = Attendee.objects.get(pk=ok.json()["id"])
        self.assertEqual((a.request_id, a.status), (link.request_id, "draft"))
        again = public.post(f"/api/v1/public/register/{token}/", _form(n=2, photo=_jpeg(), docScan=_jpeg("d.jpg")), format="multipart")
        self.assertEqual(again.status_code, 410)
        self.assertEqual(public.get(f"/api/v1/public/register/{token}/").status_code, 410)

    def test_multi_link_moves_to_new_request_after_send(self):
        made = self.op_client.post(f"/api/v1/events/{self.event.id}/registration-links/", {"link_type": "multi"}, format="json")
        token = made.json()["results"][0]["token"]
        link = RegistrationLink.objects.get(token=token)
        Request.objects.filter(pk=link.request_id).update(status="Sent")
        ok = APIClient().post(f"/api/v1/public/register/{token}/", _form(photo=_jpeg(), docScan=_jpeg("d.jpg")), format="multipart")
        self.assertEqual(ok.status_code, 201, ok.content)
        link.refresh_from_db()
        self.assertNotEqual(Attendee.objects.get(pk=ok.json()["id"]).request.status, "Sent")
        self.assertEqual(Attendee.objects.get(pk=ok.json()["id"]).request_id, link.request_id)
        self.assertEqual(self.op_client.delete(f"/api/v1/registration-links/{link.id}/").status_code, 204)
        self.assertEqual(APIClient().get(f"/api/v1/public/register/{token}/").status_code, 410)


class ApiTokenTests(Stage2Base):
    def test_external_intake(self):
        made = self.op_client.post(f"/api/v1/events/{self.event.id}/api-tokens/", {"name": "KazExpo"}, format="json")
        self.assertEqual(made.status_code, 201, made.content)
        token = made.json()["token"]
        self.assertNotIn("token", self.op_client.get(f"/api/v1/events/{self.event.id}/api-tokens/").json()["results"][0])
        ext = APIClient()
        url = f"/api/v1/external/events/{self.event.id}/attendees/"
        self.assertEqual(ext.post(url, _form(), format="json").status_code, 401)
        ext.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        ok = ext.post(url, _form(), format="json")
        self.assertEqual(ok.status_code, 201, ok.content)
        self.assertEqual(Attendee.objects.get(pk=ok.json()["id"]).request.source, "api")
        dup = ext.post(url, _form(), format="json")
        self.assertEqual(dup.status_code, 400)
        row = ApiToken.objects.get()
        self.assertIsNotNone(row.last_used_at)
        self.op_client.delete(f"/api/v1/api-tokens/{row.id}/")
        self.assertEqual(ext.post(url, _form(n=3), format="json").status_code, 401)


class AuditLogTests(Stage2Base):
    def test_admin_only(self):
        admin = APIClient()
        admin.force_authenticate(self.admin)
        self.op_client.post(f"/api/v1/events/{self.event.id}/custom-fields/", {"field_name": "x"}, format="json")
        data = admin.get("/api/v1/admin/audit-log/?action=custom_field").json()
        self.assertGreaterEqual(data["count"], 1)
        self.assertEqual(self.op_client.get("/api/v1/admin/audit-log/").status_code, 403)
