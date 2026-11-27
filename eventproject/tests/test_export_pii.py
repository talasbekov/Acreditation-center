"""Exercise the lifetime of the ZIP owned by the Django response."""

import io
import os
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

    def test_response_streams_a_private_archive_and_closes_it(self):
        with patch.object(export_service, "write_package", wraps=export_service.write_package) as write:
            response = self.client.post(self._url())
        self.assertEqual(response.status_code, 200)
        archive = write.call_args.args[0]
        self.assertTrue(hasattr(archive, "read"), "The response must own the same file used to write the ZIP")
        self.assertFalse(archive.closed)
        if isinstance(archive.name, (str, bytes)):
            # Windows delete-on-close also denies a separate ordinary reader.
            with self.assertRaises((PermissionError, FileNotFoundError)):
                with open(archive.name, "rb"):
                    pass

        payload = b"".join(response.streaming_content)
        self.assertEqual(int(response["Content-Length"]), len(payload))
        with zipfile.ZipFile(io.BytesIO(payload)) as exported:
            self.assertIn("attendees.json", exported.namelist())
        self.assertTrue(archive.closed)
        if isinstance(archive.name, (str, bytes)):
            self.assertFalse(os.path.exists(archive.name))

    def test_closing_an_unread_response_releases_the_private_archive(self):
        with patch.object(export_service, "write_package", wraps=export_service.write_package) as write:
            response = self.client.post(self._url())
        archive = write.call_args.args[0]
        try:
            self.assertFalse(archive.closed)
        finally:
            response.close()
        self.assertTrue(archive.closed)
        if isinstance(archive.name, (str, bytes)):
            self.assertFalse(os.path.exists(archive.name))

    def test_failed_archive_write_releases_file_without_exporting_rows(self):
        with patch.object(export_service, "write_package", side_effect=OSError("test write failure")) as write:
            with self.assertRaises(OSError):
                self.client.post(self._url())
        self.assertTrue(write.call_args.args[0].closed)
        self.assertFalse(ExportLog.objects.exists())
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.status, "ready")

    def test_partial_reselection_returns_conflict_and_leaves_ready_rows_pending(self):
        changed = self._mk("ready", is_resident=False, iin=None)
        write_archive = export_service.write_package

        def write_before_review(file, pairs, packaged_at):
            manifest = write_archive(file, pairs, packaged_at)
            # A review finishes before the exporter reacquires the rows.
            Attendee.objects.filter(pk=changed.pk).update(status="in_review")
            return manifest

        with patch.object(export_service, "write_package", side_effect=write_before_review) as write:
            response = self.client.post(self._url())
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.streaming)
        self.assertFalse(ExportLog.objects.exists())
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.status, "ready")
        self.assertTrue(write.call_args.args[0].closed)
