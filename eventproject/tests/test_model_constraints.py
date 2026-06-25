"""BE-7 / BE-9 — DB-level целостность: уникальность Category и валидность статуса."""

from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from directories.models import Country  # noqa: F401 (для согласованности окружения)
from eventproject.models import Attendee, Category, Event, Operator, Request
from django.contrib.auth.models import User


def _event():
    return Event.objects.create(name_rus="E", title="E")


class CategoryUniqueConstraintTests(TestCase):
    """BE-7: (event, name) уникальна — нельзя две одноимённые категории в событии."""

    def setUp(self):
        self.event = _event()
        self.other = _event()

    def test_duplicate_name_in_same_event_rejected(self):
        Category.objects.create(event=self.event, name="VIP")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(event=self.event, name="VIP")

    def test_same_name_in_different_events_allowed(self):
        Category.objects.create(event=self.event, name="VIP")
        # та же строка имени, но другое событие — допустимо.
        Category.objects.create(event=self.other, name="VIP")
        self.assertEqual(Category.objects.filter(name="VIP").count(), 2)


class AttendeeStatusConstraintTests(TestCase):
    """BE-9: DB-CheckConstraint на Attendee.status — мусорный статус отклоняется."""

    def setUp(self):
        self.event = _event()
        u = User.objects.create_user(username="op", password="x")
        self.op = Operator.objects.create(user=u, role="operator", patronymic="Т")
        self.req = Request.objects.create(
            name="R", event=self.event, status="Active", created_by=self.op,
            registration_time=timezone.now(),
        )

    def _attendee(self, **over):
        data = dict(
            surname="И", firstname="И", post="P", countryId="1000000105",
            docTypeId="ID", docSeries="AB", docIssue="МВД", sexId="M",
            visitObjects="З", transcription="I", request=self.req,
            dateAdd=timezone.now(), birthDate=date(1990, 1, 1), status="draft",
        )
        data.update(over)
        return Attendee.objects.create(**data)

    def test_valid_status_allowed(self):
        a = self._attendee(status="submitted")
        self.assertEqual(a.status, "submitted")

    def test_invalid_status_rejected_by_db(self):
        a = self._attendee()
        a.status = "bogus"
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                a.save()
