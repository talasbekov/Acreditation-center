from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
from eventproject.models import Event, Request, Attendee, Operator, ExportLog

class ExportLogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.operator = Operator.objects.create(
            user=self.user,
            patronymic="Testovich",
            phone_number="+77001234567",
            workplace="Test office"
        )
        self.event = Event.objects.create(
            name_rus="Тестовое событие",
            name_kaz="Тест",
            name_eng="Test Event",
            event_code="TEST01",
            date_start=date.today(),
            date_end=date.today() + timedelta(days=7),
            city_code="ALA"
        )
        self.request = Request.objects.create(
            name="Тестовая категория",
            event=self.event,
            status="active",
            created_by=self.operator,
            registration_time=timezone.now()
        )

    def test_exportlog_creation_with_category(self):
        """AC-1, AC-5: Create ExportLog with all fields including category."""
        now = timezone.now()
        log = ExportLog.objects.create(
            event=self.event,
            category=self.request,
            exported_before=now,
            user=self.user,
            attendee_count=10
        )
        self.assertEqual(log.event, self.event)
        self.assertEqual(log.category, self.request)
        self.assertEqual(log.exported_before, now)
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.attendee_count, 10)
        self.assertIsNotNone(log.created_at)

    def test_exportlog_creation_without_category(self):
        """AC-5: Create ExportLog without category (nullable)."""
        log = ExportLog.objects.create(
            event=self.event,
            category=None,
            exported_before=timezone.now(),
            attendee_count=5
        )
        self.assertIsNone(log.category)
        self.assertEqual(log.attendee_count, 5)

    def test_delta_filter_logic(self):
        """AC-2, AC-5: Verify delta filter logic using dateAdd."""
        base_time = timezone.now() - timedelta(hours=1)
        
        # This attendee should be INCLUDED (added AFTER exported_before)
        a1 = Attendee.objects.create(
            surname="New", firstname="User", patronymic="P",
            birthDate=date(1990, 1, 1), post="P", countryId="1",
            docTypeId="1", docSeries="A", docNumber="1",
            docBegin=date(2020, 1, 1), docEnd=date(2030, 1, 1),
            docIssue="I", sexId="M", dateAdd=base_time + timedelta(minutes=30),
            visitObjects="O", transcription="T", request=self.request,
            stickId="S"
        )
        
        # This attendee should be EXCLUDED (added BEFORE or AT exported_before)
        a2 = Attendee.objects.create(
            surname="Old", firstname="User", patronymic="P",
            birthDate=date(1990, 1, 1), post="P", countryId="1",
            docTypeId="1", docSeries="A", docNumber="2",
            docBegin=date(2020, 1, 1), docEnd=date(2030, 1, 1),
            docIssue="I", sexId="M", dateAdd=base_time - timedelta(minutes=30),
            visitObjects="O", transcription="T", request=self.request,
            stickId="S"
        )

        log = ExportLog.objects.create(
            event=self.event,
            exported_before=base_time,
            attendee_count=1
        )

        # Delta query logic from AC-2
        queryset = Attendee.objects.filter(
            dateAdd__gt=log.exported_before,
            request__event=log.event
        )

        self.assertIn(a1, queryset)
        self.assertNotIn(a2, queryset)
        self.assertEqual(queryset.count(), 1)

    def test_str_representation(self):
        """AC-5: Test __str__ method."""
        log = ExportLog.objects.create(
            event=self.event,
            category=self.request,
            exported_before=timezone.now(),
            attendee_count=0
        )
        expected_str = f"ExportLog {self.event} / {self.request.name} @ {log.exported_before}"
        self.assertEqual(str(log), expected_str)
