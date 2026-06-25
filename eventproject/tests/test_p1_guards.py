"""Production-readiness Batch B — P1 robustness guards on legacy views.

Each test reproduces a path that currently raises an *unhandled* exception (→ HTTP 500)
on malformed input or missing fixtures, and pins the desired graceful behaviour:

* P1-1  update_attendee / add_attendee with no ``Operator`` row → 403, not 500.
* P1-2  user_login (RU/KZ/EN) without username/password → friendly re-render, not 500.
* P1-3  add_attendee (RU/KZ/EN) with a malformed date → friendly error, not 500.
* P1-4  add_attendee (RU/KZ/EN): missing ``citizenship`` / a KZ-resident with no
        ``category`` field (the residency toggle hides it) → no KeyError 500. This also
        pins the RU sentinel fix (``1000000105aaaa`` typo → ``1000000105``).

The test client is built with ``raise_request_exception=False`` so an unhandled view
exception surfaces as a 500 *response* (clean RED) instead of propagating into the test.
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone

from eventproject.models import Attendee, Event, Operator, Request

VALID_IIN = "900101300007"
KZ = "1000000105"
NON_KZ = "1000000840"

ADD_ENDPOINTS = [
    "/add_attendee/{rid}/",
    "/kz/add_attendee/{rid}/",
    "/en/add_attendee/{rid}/",
]
LOGIN_ENDPOINTS = ["/user_login/", "/kz/user_login/", "/en/user_login/"]


class P1GuardTest(TestCase):
    def setUp(self):
        cache.clear()
        # raise_request_exception=False → unhandled view exceptions become 500 responses.
        self.client = Client(raise_request_exception=False)
        self.user = User.objects.create_user(username="op", password="password123")
        self.operator = Operator.objects.create(
            user=self.user,
            patronymic="Test",
            phone_number="+70000000000",
            workplace="Test Workplace",
        )
        self.event = Event.objects.create(
            name_rus="Test Event",
            name_kaz="Test Event",
            name_eng="Test Event",
            event_code="T1",
            date_start=date.today(),
            date_end=date.today(),
            city_code="AK",
        )
        self.req = Request.objects.create(
            name="Test Request",
            event=self.event,
            status="Active",
            created_by=self.operator,
            registration_time=timezone.now(),
        )
        self.client.force_login(self.user)

    def _upload(self, name="f.jpg"):
        return SimpleUploadedFile(name, b"x" * 2048, content_type="image/jpeg")

    def _payload(self, **overrides):
        data = {
            "req_id": self.req.id,
            "csrfmiddlewaretoken": "known-token",
            "last_name": "Тестовский",
            "first_name": "Иван",
            "patronymic": "Петрович",
            "latin_name": "Ivan Testovskiy",
            "iin": VALID_IIN,
            "dob": "1990-01-01",
            "sex": "M",
            "citizenship": KZ,
            "post": "Инженер",
            "document_type": "passport",
            "doc_series": "AA",
            "doc_number": "123456",
            "doc_date_start": "2020-01-01",
            "doc_date_end": "2030-01-01",
            "doc_issuer": "МВД",
            "visit_objects": "Объект",
            "category": "CAT",
            "photo": self._upload("photo.jpg"),
            "doc_photo": self._upload("doc.jpg"),
        }
        data.update(overrides)
        return data

    def _post(self, endpoint, _client=None, **overrides):
        client = _client or self.client
        return client.post(
            endpoint.format(rid=self.req.id),
            self._payload(**overrides),
            REMOTE_ADDR="127.0.0.1",
        )

    def _create_attendee(self, **overrides):
        defaults = dict(
            surname="Тестовский",
            firstname="Иван",
            patronymic="Петрович",
            transcription="Ivan Testovskiy",
            iin=VALID_IIN,
            birthDate=date(1990, 1, 1),
            post="Инженер",
            countryId=KZ,
            docTypeId="passport",
            docSeries="AA",
            docNumber="123456",
            docBegin=date(2020, 1, 1),
            docEnd=date(2030, 1, 1),
            docIssue="МВД",
            photo=self._upload("photo.jpg"),
            docScan=self._upload("doc.jpg"),
            sexId="M",
            dateAdd=timezone.now(),
            visitObjects="Объект",
            request=self.req,
            dateEnd=date.today(),
            stickId="CAT",
        )
        defaults.update(overrides)
        return Attendee.objects.create(**defaults)

    # ── P1-2: user_login без полей → не 500 ───────────────────────────────────
    def test_user_login_missing_fields_no_500(self):
        anon = Client(raise_request_exception=False)
        for path in LOGIN_ENDPOINTS:
            with self.subTest(path=path):
                resp = anon.post(path, {}, REMOTE_ADDR="127.0.0.1")
                self.assertNotEqual(resp.status_code, 500)

    # ── P1-3: битая дата → дружелюбная ошибка, не 500, ничего не сохранено ────
    def test_add_attendee_malformed_date_no_500(self):
        for endpoint in ADD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                Attendee.objects.all().delete()
                cache.clear()
                resp = self._post(endpoint, dob="not-a-date")
                self.assertNotEqual(resp.status_code, 500)
                self.assertEqual(Attendee.objects.count(), 0)

    # ── P1-4: KZ-резидент без поля category → не 500 (RU sentinel-фикс) ────────
    def test_add_attendee_resident_without_category_no_500(self):
        for endpoint in ADD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                Attendee.objects.all().delete()
                cache.clear()
                payload = self._payload(citizenship=KZ)
                payload.pop("category")
                resp = self.client.post(
                    endpoint.format(rid=self.req.id), payload, REMOTE_ADDR="127.0.0.1"
                )
                self.assertNotEqual(resp.status_code, 500)
                self.assertEqual(
                    Attendee.objects.filter(surname="Тестовский").count(), 1
                )

    # ── P1-4: отсутствует citizenship → не 500 ────────────────────────────────
    def test_add_attendee_missing_citizenship_no_500(self):
        for endpoint in ADD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                Attendee.objects.all().delete()
                cache.clear()
                payload = self._payload()
                payload.pop("citizenship")
                resp = self.client.post(
                    endpoint.format(rid=self.req.id), payload, REMOTE_ADDR="127.0.0.1"
                )
                self.assertNotEqual(resp.status_code, 500)

    # ── P1-1: update_attendee без строки Operator → 403, не 500 ───────────────
    def test_update_attendee_without_operator_returns_403(self):
        noop = User.objects.create_user(username="noop", password="password123")
        attendee = self._create_attendee()
        client = Client(raise_request_exception=False)
        client.force_login(noop)
        resp = client.post(
            "/update_attendee/%d/" % attendee.id,
            self._payload(),
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(resp.status_code, 403)

    # ── P1-1 (twin): add_attendee POST без строки Operator → 403, не 500 ──────
    def test_add_attendee_without_operator_returns_403(self):
        noop = User.objects.create_user(username="noop2", password="password123")
        client = Client(raise_request_exception=False)
        client.force_login(noop)
        for endpoint in ADD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                cache.clear()
                resp = self._post(endpoint, _client=client)
                self.assertEqual(resp.status_code, 403)

    # ── P1-1 (twin): add_attendee GET без строки Operator → 403, не 500 ───────
    def test_add_attendee_get_without_operator_returns_403(self):
        noop = User.objects.create_user(username="noop3", password="password123")
        client = Client(raise_request_exception=False)
        client.force_login(noop)
        for endpoint in ADD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                resp = client.get(
                    endpoint.format(rid=self.req.id), REMOTE_ADDR="127.0.0.1"
                )
                self.assertEqual(resp.status_code, 403)

    # ── BE-18: require_operator — Operator или PermissionDenied (→403) ────────
    def test_require_operator_helper(self):
        from django.core.exceptions import PermissionDenied
        from eventproject.view_helpers import require_operator

        self.assertEqual(require_operator(self.user), self.operator)
        noop = User.objects.create_user(username="noop4", password="x")
        with self.assertRaises(PermissionDenied):
            require_operator(noop)

    # ── BE-19: отсутствующее поле данных (не дата/citizenship) → не 500 ───────
    def test_add_attendee_missing_data_field_no_500(self):
        for endpoint in ADD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                Attendee.objects.all().delete()
                cache.clear()
                payload = self._payload()
                payload.pop("visit_objects")  # раньше KeyError 500 на bracket-доступе
                resp = self.client.post(
                    endpoint.format(rid=self.req.id), payload, REMOTE_ADDR="127.0.0.1"
                )
                self.assertNotEqual(resp.status_code, 500)
