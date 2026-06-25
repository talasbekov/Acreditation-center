"""BE-12 — пересчёт is_resident из countryId (миграция 0024)."""

import importlib
from datetime import date

from django.apps import apps as global_apps
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from eventproject.models import Attendee, Event, Operator, Request

_mig = importlib.import_module(
    "eventproject.migrations.0024_recompute_is_resident"
)


class RecomputeIsResidentTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(name_rus="E", title="E")
        u = User.objects.create_user(username="op", password="x")
        self.op = Operator.objects.create(user=u, role="operator", patronymic="Т")
        self.req = Request.objects.create(
            name="R", event=self.event, status="Active", created_by=self.op,
            registration_time=timezone.now(),
        )

    def _attendee(self, **over):
        data = dict(
            surname="И", firstname="И", post="P", docTypeId="ID", docSeries="AB",
            docIssue="МВД", sexId="M", visitObjects="З", transcription="I",
            request=self.req, dateAdd=timezone.now(), birthDate=date(1990, 1, 1),
            status="draft",
        )
        data.update(over)
        return Attendee.objects.create(**data)

    def test_recompute_corrects_historic_rows(self):
        # Резидент КЗ, ошибочно is_resident=False; нерезидент, ошибочно True.
        resident = self._attendee(countryId="1000000105", is_resident=False)
        nonresident = self._attendee(countryId="1000000840", is_resident=True)
        already_ok = self._attendee(countryId="1000000105", is_resident=True)

        _mig.recompute_is_resident(global_apps, None)

        resident.refresh_from_db()
        nonresident.refresh_from_db()
        already_ok.refresh_from_db()
        self.assertTrue(resident.is_resident)
        self.assertFalse(nonresident.is_resident)
        self.assertTrue(already_ok.is_resident)
