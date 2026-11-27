"""Этап C — повторяемый экспорт: поздняя готовность, неизменяемый пакет,
повторная выдача и подтверждение получателя."""

import hashlib
import io
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from datetime import timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from eventproject.models import Attendee, ExportLog
from eventproject.services import export as export_service
from eventproject.tests.test_export_delta import ExportDeltaBase

_MEDIA = tempfile.mkdtemp(prefix="export-packages-")


def _jpeg(name):
    return SimpleUploadedFile(name, b"\xff\xd8\xff" + os.urandom(64) + b"0" * 1500, content_type="image/jpeg")


def _payload(response):
    # The test client closes the streamed file after the last chunk. An explicit
    # response.close() would fire request_finished and drop the PostgreSQL
    # connection inside the TestCase transaction.
    return b"".join(response.streaming_content)


def _ids_in(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return [row["attendee_id"] for row in json.loads(archive.read("attendees.json"))]


class PackageTestBase(ExportDeltaBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.super_user)

    def _export(self):
        # The POST forms the package and answers 303; the file comes from a GET.
        return self.client.post(self._url(), follow=True)

    def _download_url(self, log):
        return f"/export_package/{log.package_id}/download/"

    def _ack_url(self, log):
        return f"/export_package/{log.package_id}/acknowledge/"


class LateReadinessTests(PackageTestBase):
    def test_card_approved_after_previous_export_goes_into_next_package(self):
        # Карточка создана до первой выгрузки, но одобрена после неё.
        late = self._mk("in_review", dateAdd=timezone.now() - timedelta(days=2))
        early = self._mk("ready", dateAdd=timezone.now() - timedelta(days=1))

        first = self._export()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(_ids_in(_payload(first)), [early.id])

        Attendee.objects.filter(pk=late.pk).update(status="ready")
        second = self._export()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(_ids_in(_payload(second)), [late.id])

        late.refresh_from_db()
        self.assertEqual(late.status, "exported")
        self.assertEqual(
            [log.attendee_ids for log in ExportLog.objects.order_by("id")], [[early.id], [late.id]],
        )
        third = self._export()
        self.assertIn("Нет новых записей", third.content.decode())
        self.assertEqual(ExportLog.objects.count(), 2)


@override_settings(MEDIA_ROOT=_MEDIA)
class PackageRecordTests(PackageTestBase):
    def test_package_records_identity_members_and_manifest(self):
        a = self._mk("ready", photo=_jpeg("p.jpg"), doc=_jpeg("d.jpg"))
        b = self._mk("ready", is_resident=False, iin=None, photo="", doc="")
        response = self._export()
        payload = _payload(response)
        log = ExportLog.objects.get()

        self.assertEqual(response["X-Export-Package-Id"], str(log.package_id))
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(log.attendee_ids, [a.id, b.id])
        self.assertEqual(log.archive_sha256, hashlib.sha256(payload).hexdigest())
        stamp = log.exported_before.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.assertEqual(
            log.archive_name, f"export_{self.event.id}_Охрана_{stamp}_{log.package_id.hex[:8]}.zip",
        )
        self.assertIn(log.package_id.hex[:8], response["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            self.assertEqual(names, [f"photos/{a.id}.jpg", f"documents/{a.id}.jpg", "attendees.json"])
            self.assertEqual(
                log.manifest,
                {
                    n: {
                        "sha256": hashlib.sha256(archive.read(n)).hexdigest(),
                        "size": archive.getinfo(n).file_size,
                        "crc32": archive.getinfo(n).CRC,
                    }
                    for n in names
                },
            )
            # Stored, not deflated: the size is known up front and ranges map to bytes.
            self.assertEqual({i.compress_type for i in archive.infolist()}, {zipfile.ZIP_STORED})
            rows = json.loads(archive.read("attendees.json"))
        self.assertEqual({row["status"] for row in rows}, {"ready"})

    def test_packages_formed_in_the_same_second_get_distinct_file_names(self):
        moment = timezone.now().replace(microsecond=0)
        with patch("eventproject.views.export.timezone.now", return_value=moment):
            self._mk("ready", is_resident=False, iin=None, photo="", doc="")
            _payload(self._export())
            self._mk("ready", is_resident=False, iin=None, photo="", doc="")
            _payload(self._export())
        names = list(ExportLog.objects.order_by("id").values_list("archive_name", flat=True))
        self.assertEqual(len(names), 2)
        self.assertNotEqual(names[0], names[1])

    def test_post_answers_303_to_the_package_file(self):
        self._mk("ready", is_resident=False, iin=None, photo="", doc="")
        response = self.client.post(self._url())
        log = ExportLog.objects.get()
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], self._download_url(log))
        self.assertEqual(response["X-Export-Package-Id"], str(log.package_id))
        self.assertEqual(response["X-Export-Archive-SHA256"], log.archive_sha256)

    def test_archive_is_deterministic_for_the_same_package_time(self):
        a = self._mk("ready", photo=_jpeg("p.jpg"), doc=_jpeg("d.jpg"))
        moment = timezone.now()
        outputs = []
        for _ in range(2):
            pairs = export_service.prepare_package_objects([Attendee.objects.get(pk=a.pk)])
            manifest, _ = export_service.describe_package(pairs)
            outputs.append(b"".join(export_service.package_stream(pairs, manifest, moment).iter_bytes()))
        self.assertEqual(outputs[0], outputs[1])
        utc = moment.astimezone(dt_timezone.utc)
        with zipfile.ZipFile(io.BytesIO(outputs[0])) as archive:
            stamps = {info.date_time for info in archive.infolist()}
        # Время в ZIP (DOS) хранится с шагом 2 секунды.
        self.assertEqual(stamps, {(utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second // 2 * 2)})


@override_settings(MEDIA_ROOT=_MEDIA)
class RedownloadTests(PackageTestBase):
    def _exported(self):
        self.member = self._mk("ready", photo=_jpeg("p.jpg"), doc=_jpeg("d.jpg"))
        first = self._export()
        self.original_disposition = first["Content-Disposition"]
        self.original = _payload(first)
        return ExportLog.objects.get()

    def test_redownload_returns_byte_identical_archive_and_audits(self):
        log = self._exported()
        with patch("eventproject.views.export.audit_log") as audit:
            response = self.client.post(self._download_url(log))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Export-Package-Id"], str(log.package_id))
        self.assertEqual(response["Content-Disposition"], self.original_disposition)
        self.assertEqual(int(response["Content-Length"]), len(self.original))
        self.assertEqual(_payload(response), self.original)
        self.assertEqual([c.kwargs["action"] for c in audit.call_args_list], ["export.redownload"])
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, "exported")
        self.assertEqual(ExportLog.objects.count(), 1)

    def test_changed_attendee_data_blocks_redownload(self):
        log = self._exported()
        Attendee.objects.filter(pk=self.member.pk).update(surname="Изменено")
        with patch("eventproject.views.export.audit_log") as audit:
            response = self.client.post(self._download_url(log))
        self.assertEqual(response.status_code, 409)
        self.assertIn("attendees.json", response.content.decode())
        self.assertEqual([c.kwargs["action"] for c in audit.call_args_list], ["export.redownload_refused"])

    def test_missing_media_blocks_redownload(self):
        log = self._exported()
        os.remove(self.member.photo.path)
        response = self.client.post(self._download_url(log))
        self.assertEqual(response.status_code, 409)
        self.assertIn(f"photos/{self.member.id}.jpg", response.content.decode())

    def test_replaced_media_blocks_redownload(self):
        log = self._exported()
        with open(self.member.docScan.path, "wb") as handle:
            handle.write(b"\xff\xd8\xff" + b"1" * 1500)
        response = self.client.post(self._download_url(log))
        self.assertEqual(response.status_code, 409)
        self.assertIn(f"documents/{self.member.id}.jpg", response.content.decode())

    def test_deleted_member_blocks_redownload(self):
        log = self._exported()
        Attendee.objects.filter(pk=self.member.pk).delete()
        response = self.client.post(self._download_url(log))
        self.assertEqual(response.status_code, 409)

    def test_legacy_package_without_members_is_gone(self):
        legacy = ExportLog.objects.create(
            event=self.event, category=self.category, exported_before=timezone.now(),
            user=self.super_user, attendee_count=3,
        )
        response = self.client.post(self._download_url(legacy))
        self.assertEqual(response.status_code, 410)

    def test_unknown_package_is_404(self):
        response = self.client.post(f"/export_package/{uuid.uuid4()}/download/")
        self.assertEqual(response.status_code, 404)

    def test_get_serves_the_same_archive_for_resumable_browser_downloads(self):
        log = self._exported()
        response = self.client.get(self._download_url(log))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(response["ETag"], f'"{log.archive_sha256}"')
        self.assertEqual(_payload(response), self.original)

    def test_range_request_returns_the_matching_slice(self):
        log = self._exported()
        size = len(self.original)
        for header, (start, end) in (
            ("bytes=0-99", (0, 100)),
            (f"bytes=100-{size - 50}", (100, size - 49)),
            ("bytes=-30", (size - 30, size)),
            ("bytes=1000-", (1000, size)),
        ):
            with self.subTest(header=header):
                response = self.client.get(self._download_url(log), HTTP_RANGE=header)
                self.assertEqual(response.status_code, 206)
                self.assertEqual(response["Content-Range"], f"bytes {start}-{end - 1}/{size}")
                self.assertEqual(int(response["Content-Length"]), end - start)
                self.assertEqual(_payload(response), self.original[start:end])

    def test_resume_after_cut_reassembles_the_original(self):
        log = self._exported()
        cut = len(self.original) // 3
        head = _payload(self.client.get(self._download_url(log), HTTP_RANGE=f"bytes=0-{cut - 1}"))
        tail = self.client.get(
            self._download_url(log), HTTP_RANGE=f"bytes={cut}-", HTTP_IF_RANGE=f'"{log.archive_sha256}"',
        )
        self.assertEqual(tail.status_code, 206)
        self.assertEqual(head + _payload(tail), self.original)

    def test_stale_if_range_returns_the_full_archive(self):
        log = self._exported()
        response = self.client.get(self._download_url(log), HTTP_RANGE="bytes=10-", HTTP_IF_RANGE='"other"')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_payload(response), self.original)

    def test_range_outside_archive_is_416(self):
        log = self._exported()
        response = self.client.get(self._download_url(log), HTTP_RANGE=f"bytes={len(self.original)}-")
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response["Content-Range"], f"bytes */{len(self.original)}")

    def test_same_size_replacement_aborts_the_stream_and_audits(self):
        log = self._exported()
        with open(self.member.photo.path, "r+b") as handle:
            handle.seek(10)
            handle.write(b"XX")
        response = self.client.get(self._download_url(log))
        self.assertEqual(response.status_code, 200)
        with patch("eventproject.views.export.audit_log") as audit:
            with self.assertRaises(export_service.ExportSourceChanged):
                _payload(response)
        call = audit.call_args
        self.assertEqual(call.kwargs["action"], "export.redownload_refused")
        self.assertEqual(call.kwargs["extra"]["changed"], [f"photos/{self.member.id}.jpg"])

    def test_package_from_the_earlier_manifest_format_is_gone(self):
        log = self._exported()
        legacy = {name: value["sha256"] for name, value in log.manifest.items()}
        ExportLog.objects.filter(pk=log.pk).update(manifest=legacy)
        response = self.client.post(self._download_url(log))
        self.assertEqual(response.status_code, 410)

    def test_redownload_requires_superoperator(self):
        log = self._exported()
        self.client.force_login(self.op_user)
        self.assertEqual(self.client.get(self._download_url(log)).status_code, 403)
        self.assertEqual(self.client.post(self._download_url(log)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(self._download_url(log)).status_code, 302)


class AcknowledgeTests(PackageTestBase):
    def setUp(self):
        super().setUp()
        self._mk("ready", is_resident=False, iin=None, photo="", doc="")
        _payload(self._export())
        self.log = ExportLog.objects.get()

    def test_acknowledge_records_once_and_redirects_to_dashboard(self):
        with patch("eventproject.views.export.audit_log") as audit:
            response = self.client.post(self._ack_url(self.log))
            self.assertRedirects(response, f"/dashboard/{self.event.id}/", fetch_redirect_response=False)
            self.log.refresh_from_db()
            first = self.log.acknowledged_at
            self.assertIsNotNone(first)
            self.assertEqual(self.log.acknowledged_by, self.super_user)
            self.client.post(self._ack_url(self.log))
        self.log.refresh_from_db()
        self.assertEqual(self.log.acknowledged_at, first)
        self.assertEqual([c.kwargs["action"] for c in audit.call_args_list], ["export.acknowledge"])

    def test_export_alone_is_not_an_acknowledgement(self):
        self.assertIsNone(self.log.acknowledged_at)

    def test_acknowledge_requires_superoperator(self):
        self.client.force_login(self.op_user)
        self.assertEqual(self.client.post(self._ack_url(self.log)).status_code, 403)
        self.log.refresh_from_db()
        self.assertIsNone(self.log.acknowledged_at)


class DashboardPackagesTests(PackageTestBase):
    def test_dashboard_lists_packages_with_actions(self):
        self._mk("ready", is_resident=False, iin=None, photo="", doc="")
        _payload(self._export())
        log = ExportLog.objects.get()
        legacy = ExportLog.objects.create(
            event=self.event, category=self.category,
            exported_before=timezone.now() - timedelta(days=1), attendee_count=1,
        )
        page = self.client.get(f"/dashboard/{self.event.id}/").content.decode()
        self.assertIn(str(log.package_id), page)
        self.assertIn(self._download_url(log), page)
        self.assertIn(self._ack_url(log), page)
        self.assertIn(str(legacy.package_id), page)
        self.assertNotIn(self._download_url(legacy), page)
        self.assertIn("Повторная выдача недоступна", page)


class ConsistencyUnderLockTests(PackageTestBase):
    def test_data_change_between_archive_and_lock_returns_conflict(self):
        member = self._mk("ready", is_resident=False, iin=None, photo="", doc="")
        describe = export_service.describe_package

        def describe_then_edit(pairs):
            result = describe(pairs)
            Attendee.objects.filter(pk=member.pk).update(post="Новая должность")
            return result

        with patch.object(export_service, "describe_package", side_effect=describe_then_edit):
            response = self._export()
        self.assertEqual(response.status_code, 409)
        self.assertFalse(ExportLog.objects.exists())
        member.refresh_from_db()
        self.assertEqual(member.status, "ready")


class PackageMigrationTests(TransactionTestCase):
    before = [("eventproject", "0031_backfill_legacy_event_fields")]
    after = [("eventproject", "0032_exportlog_package")]

    def tearDown(self):
        # Restore the newest schema (later migrations exist beyond `after`).
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_logs_get_distinct_package_ids_and_no_members(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old_apps = executor.loader.project_state(self.before).apps
        Event = old_apps.get_model("eventproject", "Event")
        ExportLogOld = old_apps.get_model("eventproject", "ExportLog")
        event = Event.objects.create(name_rus="E", title="E", event_code="T")
        for count in (1, 2):
            ExportLogOld.objects.create(event=event, exported_before=timezone.now(), attendee_count=count)

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)
        new_apps = executor.loader.project_state(self.after).apps
        logs = list(new_apps.get_model("eventproject", "ExportLog").objects.order_by("id"))
        self.assertEqual(len({log.package_id for log in logs}), 2)
        self.assertTrue(all(log.package_id for log in logs))
        self.assertTrue(all(log.attendee_ids is None and log.manifest is None for log in logs))


def tearDownModule():
    shutil.rmtree(_MEDIA, ignore_errors=True)
