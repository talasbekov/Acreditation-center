from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from eventproject.models import Event



def _migrate_to_latest():
    """Restore the full schema for later tests, whatever the newest migration is."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())

class LegacyEventContractTests(TransactionTestCase):
    def setUp(self):
        admin = User.objects.create_superuser("event-test", "event@example.invalid", None)
        self.client.force_login(admin, backend="django.contrib.auth.backends.ModelBackend")
        self.start = date.today() + timedelta(days=2)
        self.end = self.start + timedelta(days=3)
        self.names = {"name_rus": "Образец", "name_kaz": "Үлгі", "name_eng": "Sample"}

    def api_values(self, pk):
        response = self.client.get(f"/api/v1/events/{pk}/")
        self.assertEqual(response.status_code, 200)
        return tuple(response.json()[key] for key in ("title", "start_date", "end_date"))

    def test_html_created_event_is_readable_through_api(self):
        response = self.client.post("/create_event/", {
            **self.names, "event_code": "E2E", "city": "1",
            "date_start": self.start.isoformat(), "date_end": self.end.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        event = Event.objects.get(event_code="E2E")
        self.assertEqual(self.api_values(event.pk), ("Образец", self.start.isoformat(), self.end.isoformat()))
        self.assertEqual((event.name_kaz, event.name_eng), ("Үлгі", "Sample"))

    def test_upgrade_populates_missing_api_fields_and_preserves_edited_values(self):
        previous = ("eventproject", "0025_user_session_generation")
        current = ("eventproject", "0026_backfill_legacy_event_fields")
        executor = MigrationExecutor(connection)
        executor.migrate([previous])
        self.addCleanup(_migrate_to_latest)
        events = executor.loader.project_state([previous]).apps.get_model("eventproject", "Event").objects
        old = dict(**self.names, date_start=self.start, date_end=self.end)
        plain = events.create(**old)
        start = self.start - timedelta(days=1)
        edited = events.create(**old, title="API title", start_date=start)
        end = self.end + timedelta(days=1)
        partial = events.create(**old, title="", end_date=end)
        no_source = events.create(name_kaz="Үлгі", name_eng="Sample")
        MigrationExecutor(connection).migrate([current])
        for record, expected in (
            (plain, ("Образец", self.start.isoformat(), self.end.isoformat())),
            (edited, ("API title", start.isoformat(), self.end.isoformat())),
            (partial, ("Образец", self.start.isoformat(), end.isoformat())),
            (no_source, (None, None, None)),
        ):
            with self.subTest(event=record.pk):
                self.assertEqual(self.api_values(record.pk), expected)
                record.refresh_from_db()
                self.assertEqual((record.name_kaz, record.name_eng), ("Үлгі", "Sample"))
