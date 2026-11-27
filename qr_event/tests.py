from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import QrIin


# Synthetic value with a leading zero for the historical field.
FIXTURE_IIN = "000101500001"


class QrPrivacyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.operator = user_model.objects.create_user(username="qr-fixture-operator")
        cls.admin_user = user_model.objects.create_user(
            username="qr-fixture-admin", is_staff=True, is_superuser=True,
        )

    def test_anonymous_qr_routes_require_login(self):
        for url in (reverse("iin_form"), reverse("qr_success", args=[1])):
            with self.subTest(url=url):
                response = self.client.get(url, secure=True)
                self.assertRedirects(
                    response, "/user_login/?next=" + url,
                    fetch_redirect_response=False,
                )

    def test_paused_form_does_not_collect_or_persist_iin(self):
        self.client.force_login(self.operator)
        url = reverse("iin_form")
        response = self.client.get(url, secure=True)
        self.assertContains(response, "Выдача QR-кодов временно приостановлена", status_code=503)
        self.assertNotContains(response, '<form', status_code=503)
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.post(url, {"iin": FIXTURE_IIN}, secure=True)
            self.assertEqual(response.status_code, 503)
            self.assertIn("no-store", response.headers["Cache-Control"])
            self.assertNotContains(response, FIXTURE_IIN, status_code=503)
            self.assertFalse(QrIin.objects.exists())
            self.assertEqual(list(Path(media_root).iterdir()), [])

    def test_historical_results_are_withdrawn_in_all_sessions(self):
        record = QrIin.objects.create(iin=FIXTURE_IIN, qr_code="qr_codes/historical.png")
        for user in (self.operator, self.admin_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                session = self.client.session
                session["qr_iin_created_pks"] = [record.pk]
                session.save()
                existing = self.client.get(reverse("qr_success", args=[record.pk]), secure=True)
                missing = self.client.get(reverse("qr_success", args=[record.pk + 1]), secure=True)
                self.assertEqual((existing.status_code, missing.status_code), (404, 404))
                self.assertEqual(existing.content, missing.content)
                self.assertNotIn(FIXTURE_IIN.encode(), existing.content)
                self.assertNotIn(b"historical.png", existing.content)
                self.assertIn("no-store", existing.headers["Cache-Control"])

    def test_historical_media_is_unavailable_to_all_users(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            historical = Path(media_root, "qr_codes", "historical.png")
            historical.parent.mkdir()
            historical.write_bytes(b"fixture-png-bytes")
            for user in (None, self.operator, self.admin_user):
                with self.subTest(user=user and user.username):
                    if user:
                        self.client.force_login(user)
                    response = self.client.get("/media/qr_codes/historical.png", secure=True)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn(b"fixture-png-bytes", response.content)

    def test_assigned_event_media_is_still_readable(self):
        from eventproject.models import Event, Operator

        event = Event.objects.create(
            name_rus="Fixture", name_kaz="Fixture", name_eng="Fixture", event_code="TEST",
            city_code="TEST", date_start="2026-01-01", date_end="2026-01-02",
        )
        assignment = Operator.objects.create(user=self.operator)
        assignment.events.add(event)
        relative = f"event_{event.pk}/synthetic.txt"
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            document = Path(media_root, relative)
            document.parent.mkdir()
            document.write_bytes(b"event fixture")
            self.client.force_login(self.operator)
            response = self.client.get("/media/" + relative, secure=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"event fixture")

    def test_admin_shows_only_historical_metadata(self):
        record = QrIin.objects.create(iin=FIXTURE_IIN, qr_code="qr_codes/historical.png")
        self.client.force_login(self.admin_user)
        for url in (
            reverse("admin:qr_event_qriin_changelist"),
            reverse("admin:qr_event_qriin_change", args=[record.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url, secure=True)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, FIXTURE_IIN)
                self.assertNotContains(response, "historical.png")
        self.assertFalse(admin.site._registry[QrIin].has_add_permission(response.wsgi_request))

    def test_historical_iin_remains_encrypted_at_rest(self):
        from django.db import connection

        record = QrIin.objects.create(iin=FIXTURE_IIN)
        self.assertEqual(QrIin.objects.get(pk=record.pk).iin, FIXTURE_IIN)
        with connection.cursor() as cursor:
            cursor.execute("SELECT iin FROM qr_event_qriin WHERE id = %s", [record.pk])
            stored = cursor.fetchone()[0]
        self.assertNotIn(FIXTURE_IIN, str(stored))
