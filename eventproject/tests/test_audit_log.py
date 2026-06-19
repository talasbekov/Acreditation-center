from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from eventproject.audit import audit_log
from eventproject.models import Attendee, Event, Operator, Request


class AuditLogFunctionTest(SimpleTestCase):
    def test_audit_log_authenticated_user(self):
        user = MagicMock()
        user.id = 42
        user.role = "operator"

        with patch("eventproject.audit.logger") as mock_logger:
            audit_log(user, "attendee.create", "Attendee", 99, "127.0.0.1")
            extra = mock_logger.info.call_args[1]["extra"]
            self.assertEqual(extra["user_id"], 42)
            self.assertEqual(extra["role"], "operator")
            self.assertEqual(extra["action"], "attendee.create")
            self.assertEqual(extra["obj_type"], "Attendee")
            self.assertEqual(extra["obj_id"], "99")
            self.assertEqual(extra["ip"], "127.0.0.1")

    def test_audit_log_defaults_regular_users_to_operator_role(self):
        user = MagicMock()
        user.id = 7
        user.is_superuser = False

        with patch("eventproject.audit.logger") as mock_logger:
            audit_log(user, "attendee.update", "Attendee", 1, "127.0.0.1")
            extra = mock_logger.info.call_args[1]["extra"]
            self.assertEqual(extra["role"], "operator")

    def test_audit_log_defaults_superusers_to_superuser_role(self):
        user = MagicMock()
        user.id = 1
        user.is_superuser = True

        with patch("eventproject.audit.logger") as mock_logger:
            audit_log(user, "attendee.delete", "Attendee", 2, "127.0.0.1")
            extra = mock_logger.info.call_args[1]["extra"]
            self.assertEqual(extra["role"], "superuser")

    def test_audit_log_celery_task_user_none(self):
        with patch("eventproject.audit.logger") as mock_logger:
            audit_log(None, "attendee.import_kazenergy", "Attendee", 5, "celery-worker")
            extra = mock_logger.info.call_args[1]["extra"]
            self.assertIsNone(extra["user_id"])
            self.assertEqual(extra["role"], "system")
            self.assertEqual(extra["ip"], "celery-worker")

    def test_audit_log_extra_field_included(self):
        user = MagicMock()
        user.id = 1
        user.role = "superoperator"

        with patch("eventproject.audit.logger") as mock_logger:
            audit_log(
                user,
                "attendee.update",
                "Attendee",
                10,
                "10.0.0.1",
                extra={"from": "draft", "to": "submitted"},
            )
            extra = mock_logger.info.call_args[1]["extra"]
            self.assertEqual(extra["extra"]["from"], "draft")
            self.assertEqual(extra["extra"]["to"], "submitted")

    def test_audit_log_obj_id_converted_to_str(self):
        user = MagicMock()
        user.id = 3
        user.role = "operator"

        with patch("eventproject.audit.logger") as mock_logger:
            audit_log(user, "attendee.create", "Attendee", 123, "10.0.0.2")
            extra = mock_logger.info.call_args[1]["extra"]
            self.assertIsInstance(extra["obj_id"], str)
            self.assertEqual(extra["obj_id"], "123")


class AuditLogViewIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="operator", password="password123")
        self.operator = Operator.objects.create(
            user=self.user,
            patronymic="Test",
            phone_number="+70000000000",
            workplace="Test Workplace",
        )
        self.event = Event.objects.create(
            name_rus="Test Event",
            name_kaz="Test Event",
            name_eng="Test Event",
            event_code="T1",
            date_start=date.today(),
            date_end=date.today(),
            city_code="AK",
        )
        self.req = Request.objects.create(
            name="Test Request",
            event=self.event,
            status="Active",
            created_by=self.operator,
            registration_time=timezone.now(),
        )
        self.client.force_login(self.user)

    def _upload(self, name):
        return SimpleUploadedFile(name, b"x" * 2048, content_type="image/jpeg")

    def _create_attendee(self, surname="Old"):
        return Attendee.objects.create(
            surname=surname,
            firstname="Name",
            patronymic="Patro",
            transcription="Old Name",
            iin="123456789012",
            birthDate=date(1990, 1, 1),
            post="Engineer",
            countryId="1000000105",
            docTypeId="passport",
            docSeries="AA",
            docNumber="123456",
            docBegin=date(2020, 1, 1),
            docEnd=date(2030, 1, 1),
            docIssue="Issuer",
            photo=self._upload("photo.jpg"),
            docScan=self._upload("doc.jpg"),
            sexId="M",
            dateAdd=timezone.now(),
            visitObjects="Object",
            request=self.req,
            dateEnd=date.today(),
            stickId="CAT",
        )

    def test_add_attendee_emits_audit_log(self):
        with patch("eventproject.views.attendee.audit_log") as mock_audit_log:
            response = self.client.post(
                reverse("add_attendee", args=[self.req.id]),
                {
                    "req_id": self.req.id,
                    "csrfmiddlewaretoken": "known-token",
                    "last_name": "Test",
                    "first_name": "User",
                    "patronymic": "Patro",
                    "latin_name": "Test User",
                    "iin": "123456789012",
                    "dob": "1990-01-01",
                    "sex": "M",
                    "citizenship": "1000000105",
                    "post": "Engineer",
                    "document_type": "passport",
                    "doc_series": "AA",
                    "doc_number": "123456",
                    "doc_date_start": "2020-01-01",
                    "doc_date_end": "2030-01-01",
                    "doc_issuer": "Issuer",
                    "visit_objects": "Object",
                    "category": "CAT",
                    "photo": self._upload("new-photo.jpg"),
                    "doc_photo": self._upload("new-doc.jpg"),
                },
                REMOTE_ADDR="127.0.0.1",
            )

        self.assertEqual(response.status_code, 200)
        attendee = Attendee.objects.get(surname="Test", firstname="User")
        mock_audit_log.assert_called_once_with(
            user=self.user,
            action="attendee.create",
            obj_type="Attendee",
            obj_id=attendee.id,
            ip="127.0.0.1",
        )

    def test_update_attendee_emits_audit_log(self):
        attendee = self._create_attendee()

        with patch("eventproject.views.attendee.audit_log") as mock_audit_log:
            response = self.client.post(
                reverse("update_attendee", args=[attendee.id]),
                {
                    "csrfmiddlewaretoken": "known-token",
                    "last_name": "Updated",
                    "first_name": "Name",
                    "patronymic": "Patro",
                    "latin_name": "Updated Name",
                    "iin": "123456789012",
                    "dob": "1990-01-01",
                    "sex": "M",
                    "citizenship": "1000000105",
                    "post": "Lead Engineer",
                    "document_type": "passport",
                    "doc_series": "AA",
                    "doc_number": "654321",
                    "doc_date_start": "2020-01-01",
                    "doc_date_end": "2030-01-01",
                    "doc_issuer": "Updated Issuer",
                    "visit_objects": "Updated Object",
                },
                REMOTE_ADDR="127.0.0.2",
            )

        self.assertEqual(response.status_code, 302)
        mock_audit_log.assert_called_once_with(
            user=self.user,
            action="attendee.update",
            obj_type="Attendee",
            obj_id=attendee.id,
            ip="127.0.0.2",
        )

    def test_delete_attendee_emits_audit_log(self):
        attendee = self._create_attendee("Delete")
        self._create_attendee("Keep")

        with patch("eventproject.views.attendee.audit_log") as mock_audit_log:
            response = self.client.post(
                reverse("delete_attendee"),
                {"attendee_id": attendee.id},
                REMOTE_ADDR="127.0.0.3",
            )

        self.assertEqual(response.status_code, 200)
        mock_audit_log.assert_called_once_with(
            user=self.user,
            action="attendee.delete",
            obj_type="Attendee",
            obj_id=str(attendee.id),
            ip="127.0.0.3",
        )
