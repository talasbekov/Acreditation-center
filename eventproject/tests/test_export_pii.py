"""The package archive is streamed: no temporary file or copy with personal data."""

import io
import tempfile
import zipfile
from unittest.mock import patch

from django.test import TransactionTestCase

from eventproject.models import Attendee, ExportLog
from eventproject.services import export as export_service
from eventproject.tests.test_export_delta import ExportDeltaFixtures


class ExportArchiveLifetimeTests(ExportDeltaFixtures, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.super_user)
        self.attendee = self._mk("ready", is_resident=False, iin=None)

    def test_package_is_streamed_without_a_temporary_file(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("the export must not write the archive to a temporary file")

        with patch.object(tempfile, "TemporaryFile", side_effect=forbidden), \
                patch.object(tempfile, "NamedTemporaryFile", side_effect=forbidden):
            response = self.client.post(self._url(), follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.streaming)
            payload = b"".join(response.streaming_content)
        self.assertEqual(int(response["Content-Length"]), len(payload))
        with zipfile.ZipFile(io.BytesIO(payload)) as exported:
            self.assertIn("attendees.json", exported.namelist())

    def test_failed_file_read_leaves_rows_ready(self):
        with patch.object(export_service, "describe_package", side_effect=OSError("test read failure")):
            with self.assertRaises(OSError):
                self.client.post(self._url())
        self.assertFalse(ExportLog.objects.exists())
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.status, "ready")

    def test_partial_reselection_returns_conflict_and_leaves_ready_rows_pending(self):
        changed = self._mk("ready", is_resident=False, iin=None)
        describe = export_service.describe_package

        def describe_before_review(pairs):
            result = describe(pairs)
            # A review finishes before the exporter reacquires the rows.
            Attendee.objects.filter(pk=changed.pk).update(status="in_review")
            return result

        with patch.object(export_service, "describe_package", side_effect=describe_before_review):
            response = self.client.post(self._url())
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.streaming)
        self.assertFalse(ExportLog.objects.exists())
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.status, "ready")
