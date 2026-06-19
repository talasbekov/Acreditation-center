"""H4: экспортные эндпоинты — POST+CSRF, атомарная смена статуса, аудит.

Покрывает поведение, добавленное при усилении download_*_json:
  * мутация статуса (Sent -> Exported) допустима только по POST;
  * GET суперпользователя -> 405 (require_POST);
  * аноним -> редирект на логин и статус НЕ меняется;
  * успешный POST возвращает JSON и атомарно помечает заявки Exported.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from eventproject.models import Event, Request, Attendee, Operator


class ExportViewsH4Tests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="su", password="pw12345678", email="su@example.com"
        )
        op_user = User.objects.create_user(username="op", password="pw12345678")
        self.operator = Operator.objects.create(
            user=op_user,
            patronymic="T",
            phone_number="+77001234567",
            workplace="office",
            role="operator",
        )
        self.event = Event.objects.create(
            name_rus="Событие", name_kaz="Оқиға", name_eng="Event",
            event_code="EXP01", date_start=date.today(),
            date_end=date.today() + timedelta(days=3), city_code="ALA",
        )
        self.req = Request.objects.create(
            name="Категория", event=self.event, status="Sent",
            created_by=self.operator, registration_time=timezone.now(),
        )
        Attendee.objects.create(
            surname="Иванов", firstname="Иван", patronymic="И",
            birthDate=date(1990, 1, 1), post="P", countryId="1",
            docTypeId="1", docSeries="A", docNumber="1",
            docBegin=date(2020, 1, 1), docEnd=date(2030, 1, 1),
            docIssue="I", sexId="M", dateAdd=timezone.now(),
            visitObjects="O", transcription="T", request=self.req, stickId="S",
        )

    def test_get_is_rejected_for_superuser(self):
        """GET не должен менять состояние — require_POST возвращает 405."""
        self.client.force_login(self.superuser)
        resp = self.client.get(f"/download_guests_json/{self.event.id}/")
        self.assertEqual(resp.status_code, 405)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Sent")  # статус не тронут

    def test_anonymous_cannot_export(self):
        """Аноним: редирект на логин, статус не меняется."""
        resp = self.client.get(f"/download_guests_json/{self.event.id}/")
        self.assertEqual(resp.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Sent")

    def test_post_exports_and_marks_exported(self):
        """POST суперпользователя: 200, JSON с участником, статус -> Exported."""
        self.client.force_login(self.superuser)
        resp = self.client.post(f"/download_guests_json/{self.event.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/json")
        self.assertIn("Иванов", resp.content.decode("utf-8"))
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Exported")

    def test_download_request_json_post(self):
        """Поштучный экспорт заявки также POST-only и помечает Exported."""
        self.client.force_login(self.superuser)
        get_resp = self.client.get(f"/download_request_json/{self.req.id}/")
        self.assertEqual(get_resp.status_code, 405)

        resp = self.client.post(f"/download_request_json/{self.req.id}/")
        self.assertEqual(resp.status_code, 200)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, "Exported")
