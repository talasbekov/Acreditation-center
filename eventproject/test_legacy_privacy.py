from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone

from eventproject.middleware.logging_middleware import RequestLoggingMiddleware
from eventproject.models import Attendee, Event, Operator, Request


class LegacyPrivacyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="synthetic-admin", is_superuser=True)
        operator = Operator.objects.create(user=cls.user)
        cls.event = Event.objects.create(name_rus="Fixture", date_start="2026-01-01", date_end="2026-01-02")
        cls.req = Request.objects.create(name="Private note", status="Sent", event=cls.event,
                                         created_by=operator, registration_time=timezone.now())
        cls.attendee = Attendee.objects.create(request=cls.req, surname="Private surname",
                                               dateAdd=timezone.now())

    def test_internal_reconciliation_is_repeatable_and_preserves_queue(self):
        self.client.force_login(self.user)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        row = {"id": self.attendee.pk, "request": self.req.pk}
        for name in ("download_json", "download_guests_json", "download_all_guests_json", "download_request_json"):
            with self.subTest(name=name):
                Request.objects.filter(pk=self.req.pk).update(status="Sent")
                by_request = name == "download_request_json"
                pk = self.req.pk if by_request else self.event.pk
                path = f"/{name}/{pk}/"
                self.assertEqual(self.client.get(path, secure=True).status_code, 405)
                self.assertEqual(csrf_client.post(path, secure=True).status_code, 403)
                self.req.refresh_from_db()
                self.assertEqual(self.req.status, "Sent")
                response = self.client.post(path, secure=True)
                self.assertEqual(response.status_code, 200)
                expected = {"id": pk, "attendees": [row]}
                if by_request:
                    expected["event"] = str(self.event.pk)
                self.assertEqual(response.json(), expected)
                self.req.refresh_from_db()
                self.assertEqual(self.req.status, "Sent")
                self.attendee.refresh_from_db()
                self.assertEqual(self.attendee.status, "draft")
                self.assertIn("private", response.headers["Cache-Control"])
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertEqual(self.client.post(path, secure=True).json(), expected)

    def test_request_logging_uses_only_route_metadata(self):
        middleware = RequestLoggingMiddleware(lambda request: HttpResponse())
        factory = RequestFactory()
        for match in (None, SimpleNamespace(route="operator-access/<uid>/<token>/")):
            with self.subTest(match=match):
                request = factory.get("/operator-access/fixture-id/private-marker/?key=private-query",
                                      HTTP_X_FORWARDED_FOR="private-proxy", REMOTE_ADDR="private-address")
                request.resolver_match = match
                request.user = self.user
                with self.assertLogs("request_logger", level="INFO") as captured:
                    middleware(request)
                record = captured.records[0]
                text = str(vars(record))
                for value in ("private-marker", "private-query", "private-proxy", "private-address", self.user.username):
                    self.assertNotIn(value, text)

    def test_import_preserves_acks_and_excludes_partner_data_from_diagnostics(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        import httpx
        from asgiref.sync import async_to_sync
        from eventproject.views.integration import integrate_kazenergy as partner

        incoming = {
            "id": 41, "surname": "private-surname", "firstname": "private-firstname",
            "post": "fixture", "countryId": "1", "docTypeId": "1", "docNumber": "private-doc",
            "sexId": "1", "visitObjects": "1", "transcription": "unique-synthetic",
            "dateAdd": "2026-01-01T12:00:00Z", "birthDate": "2000-01-01",
            "docBegin": "2020-01-01", "docEnd": "2030-01-01",
        }
        batches = iter([[{"id": 40, "surname": "private-surname"}], [incoming], []])
        acks = []

        def transport(request):
            if request.method == "GET":
                return httpx.Response(200, json={"attendees": next(batches)})
            acks.append(json.loads(request.content))
            return httpx.Response(200, text="private-partner-body")

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        request = RequestFactory().get("/")
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media), (
            patch.object(partner, "API_KEY", "fixture-token")
        ), patch.object(partner, "BASE_URL", "https://example.invalid/fixture"), (
            patch.object(partner, "ACK_URL", "https://example.invalid/ack")
        ), patch.object(partner.httpx, "AsyncClient", return_value=http_client), (
            self.assertLogs(partner.logger.name, "INFO")
        ) as captured:
            response = async_to_sync(partner.kazenergy_receive)(request, self.event.pk, self.req.created_by_id)
            self.assertEqual(list(Path(media).iterdir()), [])
        self.assertEqual([(ack["id"], ack["code"]) for ack in acks], [(40, 9), (41, 2)])
        # Этап C: заявка в статусе Sent не пополняется — импорт открывает новую Active.
        imported = Attendee.objects.get(transcription="unique-synthetic")
        self.assertNotEqual(imported.request_id, self.req.pk)
        self.assertEqual(imported.request.status, "Active")
        self.assertEqual(json.loads(response.content)["processed"], 2)
        diagnostic = str(captured.output) + response.content.decode()
        for marker in ("private-surname", "private-firstname", "private-doc", "fixture-token", "private-partner-body"):
            self.assertNotIn(marker, diagnostic)

    def test_framework_log_filter_keeps_http_status_only(self):
        import logging
        from eventproject.privacy_logging import HttpPrivacyFilter

        for source in ("django.request", "django.server", "django.security.csrf", "httpx", "httpcore.http11"):
            with self.subTest(source=source):
                record = logging.LogRecord(source, logging.WARNING, "", 0, "Error %s", ("private-token",), None)
                record.request = "private-request"
                record.status_code = 403
                HttpPrivacyFilter().filter(record)
                self.assertEqual(record.getMessage(), "HTTP response status=403")
                self.assertNotIn("private-", str(vars(record)))

    def test_avalon_validation_ack_creates_no_csv(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        import httpx
        from asgiref.sync import async_to_sync
        from eventproject.views.integration import integrate as partner

        replies = iter([
            httpx.Response(200, json={"attendees": [{"id": 43, "surname": "private-surname"}]}),
            httpx.Response(404),
        ])
        posted = []

        def transport(request):
            if request.method == "GET":
                return next(replies)
            posted.append(json.loads(request.content))
            return httpx.Response(200, text="private-ack-body")

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        request = RequestFactory().post("/")
        request.user = self.user
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media), (
            patch.object(partner, "AVALON_API_KEY", "fixture-key")
        ), patch.object(partner.httpx, "AsyncClient", return_value=http_client), (
            self.assertLogs(partner.logger.name, "INFO")
        ) as captured:
            response = async_to_sync(partner.kazexpo_receive)(request, self.event.pk)
            self.assertEqual(list(Path(media).iterdir()), [])
        self.assertEqual([(ack["id"], ack["code"]) for ack in posted], [(43, 1)])
        self.assertEqual(json.loads(response.content)["errors"], 1)
        self.assertNotIn("private-", str(captured.output) + response.content.decode())
