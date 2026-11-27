"""Потоковый ZIP (services/zipstream.py): формат, ZIP64, диапазоны, сверка файлов."""

import io
import os
import shutil
import tempfile
import zipfile
import zlib
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

from eventproject.services import zipstream

STAMP = (2026, 11, 27, 10, 11, 13)


class ZipStreamTests(SimpleTestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="zipstream-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.files = []
        for index, size in enumerate((0, 1, 70_000, zipstream.CHUNK_SIZE * 2 + 17)):
            path = os.path.join(self.root, f"{index}.jpg")
            data = os.urandom(size)
            with open(path, "wb") as handle:
                handle.write(data)
            self.files.append((f"photos/{index}.jpg", path, data))
        self.json = "[{\"name\": \"Жанна\"}]".encode()

    def _entries(self, known=True):
        entries = []
        for name, path, data in self.files:
            if known:
                size, crc, sha = zipstream.describe_file(path)
                entries.append(zipstream.Entry(name, size, crc, sha, path=path))
            else:
                entries.append(zipstream.Entry(name, len(data), path=path))
        crc = zlib.crc32(self.json) if known else None
        entries.append(zipstream.Entry("attendees.json", len(self.json), crc, data=self.json))
        return entries

    def _check_archive(self, blob):
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist(), [name for name, _, _ in self.files] + ["attendees.json"])
            for name, _, data in self.files:
                self.assertEqual(archive.read(name), data)
            self.assertEqual(archive.read("attendees.json"), self.json)
            self.assertEqual({info.date_time for info in archive.infolist()}, {(2026, 11, 27, 10, 11, 12)})

    def test_archive_reads_back_and_size_is_exact(self):
        for known in (True, False):
            with self.subTest(known_crc=known):
                stream = zipstream.ZipStream(self._entries(known), STAMP)
                blob = b"".join(stream.iter_bytes())
                self.assertEqual(len(blob), stream.size)
                self._check_archive(blob)

    def test_zip64_records_are_valid(self):
        # Force every ZIP64 path (sizes, offsets, entry count) on a small archive.
        with patch.object(zipstream, "ZIP64_LIMIT", 1000), patch.object(zipstream, "ZIP_FILECOUNT_LIMIT", 2):
            for known in (True, False):
                with self.subTest(known_crc=known):
                    stream = zipstream.ZipStream(self._entries(known), STAMP)
                    blob = b"".join(stream.iter_bytes())
                    self.assertEqual(len(blob), stream.size)
                    self._check_archive(blob)

    def test_any_byte_range_matches_the_full_archive(self):
        stream = zipstream.ZipStream(self._entries(), STAMP)
        blob = b"".join(stream.iter_bytes())
        size = len(blob)
        cuts = sorted({0, 1, 29, 30, 31, size // 3, size // 2, size - 23, size - 1, size})
        for start in cuts:
            for end in cuts:
                if start <= end:
                    self.assertEqual(b"".join(stream.iter_bytes(start, end)), blob[start:end], (start, end))

    def test_ranges_need_known_crc(self):
        stream = zipstream.ZipStream(self._entries(known=False), STAMP)
        self.assertFalse(stream.ranges_supported)
        with self.assertRaises(zipstream.RangeNotSatisfiable):
            list(stream.iter_bytes(10, 20))

    def test_changed_file_stops_before_its_last_byte(self):
        stream = zipstream.ZipStream(self._entries(), STAMP)
        name, path, data = self.files[3]
        new_last = b"\x00" if data[-1:] != b"\x00" else b"\x01"
        with open(path, "r+b") as handle:
            handle.seek(len(data) - 1)
            handle.write(new_last)
        received = bytearray()
        with self.assertRaises(zipstream.SourceChanged) as caught:
            for chunk in stream.iter_bytes():
                received += chunk
        self.assertEqual(caught.exception.args[0], name)
        # The changed file never left the server in full.
        self.assertLess(len(received), stream.size)
        self.assertNotIn(data[:-1] + new_last, bytes(received))

    def test_missing_or_resized_file_is_reported(self):
        for action in ("remove", "grow"):
            with self.subTest(action=action):
                self.setUp()
                stream = zipstream.ZipStream(self._entries(known=False), STAMP)
                name, path, _ = self.files[2]
                if action == "remove":
                    os.remove(path)
                else:
                    with open(path, "ab") as handle:
                        handle.write(b"extra")
                with self.assertRaises(zipstream.SourceChanged) as caught:
                    b"".join(stream.iter_bytes())
                self.assertEqual(caught.exception.args[0], name)

    def test_duplicate_names_are_rejected(self):
        entry = zipstream.Entry("a", 1, data=b"x")
        with self.assertRaises(ValueError):
            zipstream.ZipStream([entry, entry], STAMP)

    def test_parse_range(self):
        self.assertIsNone(zipstream.parse_range(None, 100))
        self.assertEqual(zipstream.parse_range("bytes=0-9", 100), (0, 10))
        self.assertEqual(zipstream.parse_range("bytes=90-", 100), (90, 100))
        self.assertEqual(zipstream.parse_range("bytes=95-500", 100), (95, 100))
        self.assertEqual(zipstream.parse_range("bytes=-10", 100), (90, 100))
        self.assertEqual(zipstream.parse_range("bytes=-500", 100), (0, 100))
        self.assertIsNone(zipstream.parse_range("bytes=0-1,5-6", 100))
        self.assertIsNone(zipstream.parse_range("items=0-1", 100))
        self.assertIsNone(zipstream.parse_range("bytes=a-b", 100))
        self.assertIsNone(zipstream.parse_range("bytes=5-2", 100))
        for header in ("bytes=100-", "bytes=-0"):
            with self.assertRaises(zipstream.RangeNotSatisfiable):
                zipstream.parse_range(header, 100)


class LegacyEventPhotosTests(TestCase):
    """`download_photos` streams all event media as one ZIP with a known length."""

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="legacy-photos-")
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        os.makedirs(os.path.join(self.media, "event_7", "photos"))
        self.photo = os.urandom(5000)
        with open(os.path.join(self.media, "event_7", "photos", "1.jpg"), "wb") as handle:
            handle.write(self.photo)
        with open(os.path.join(self.media, "event_7", ".hidden"), "wb") as handle:
            handle.write(b"x")
        self.admin = User.objects.create_superuser("root", password="Pass123!x")
        self.client.force_login(self.admin)

    def test_streams_event_media(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("no temporary archive")

        with override_settings(MEDIA_ROOT=self.media), \
                patch.object(tempfile, "NamedTemporaryFile", side_effect=forbidden):
            response = self.client.get("/download_photos/7/")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.streaming)
            payload = b"".join(response.streaming_content)
        self.assertEqual(int(response["Content-Length"]), len(payload))
        self.assertIn('filename="event_7.zip"', response["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(archive.namelist(), ["event_7/photos/1.jpg"])
            self.assertEqual(archive.read("event_7/photos/1.jpg"), self.photo)

    def test_missing_directory_is_404(self):
        with override_settings(MEDIA_ROOT=self.media):
            self.assertEqual(self.client.get("/download_photos/8/").status_code, 404)
