"""Этап E (п. 3 плана): матрица доступа «роль × метод × адрес».

Обходит все адреса проекта (кроме стандартной админки Django — она проверяется
отдельно по входу), включая KZ/EN-копии, для ролей: аноним, оператор чужого
мероприятия, оператор-владелец, супероператор, администратор. Проверяет инварианты:

* аноним получает 2xx только на публичных адресах и никогда не видит данных;
* оператор чужого мероприятия не видит данных мероприятия A и ничего в нём не меняет;
* оператор не получает 2xx на административных и проверочных адресах и ничего через них не меняет;
* файл участника отдаётся владельцу и администратору, но не анониму и не чужому оператору.

Полная таблица пишется в CSV, если задана переменная окружения ``ACCESS_MATRIX_OUT``.
"""

import csv
import os
import re
import shutil
import tempfile
import uuid
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone

from eventproject.models import Attendee, Event, Operator, Request

MARKER = "Маркерова"  # фамилия участника мероприятия A — не должна утечь посторонним

# Адреса, открытые без входа по замыслу.
PUBLIC = {
    "health/", "healthz/", "api/health/", "qr/", "qr/success/<int:pk>/", "user_login/", "",
    "api/v1/csrf/", "api/v1/public/content-manager/translations",
    "operator-access/<uidb64>/<token>/", "embankment/login/",
}
# Только администратор (is_superuser).
ADMIN_ONLY = {
    "avmac/", "create_event/", "add_operator/", "add_operator_to_event/", "show_operator/<int:operator_id>/",
    "show_event/<int:event_id>/", "delete_event/<int:event_id>/", "download_json/<int:event_id>/",
    "download_guests_json/<int:event_id>/", "download_photos/<int:event_id>/", "download_file/<int:event_id>/",
    "check_archive_status/<int:event_id>/", "download_request_json/<int:request_id>/",
    "download_all_guests_json/<int:event_id>/", "show_request_to_admin/<int:request_id>/", "bind_operators/",
    "new_password/<str:username>/", "delete_operator/<str:username>/",
    "unbind_event/<int:event_id>/<str:username>/", "embankment/",
    # API страниц администратора Next.js (views/admin_api.py).
    "api/v1/admin/home/", "api/v1/admin/events/", "api/v1/admin/events/<int:event_id>/",
    "api/v1/admin/events/<int:event_id>/operators/", "api/v1/admin/events/<int:event_id>/operators/<int:operator_id>/",
    "api/v1/admin/operators/", "api/v1/admin/operators/<int:operator_id>/",
    "api/v1/admin/operators/<int:operator_id>/new-password/", "api/v1/admin/audit-log/",
}
# Проверяющий (супероператор) и администратор.
REVIEW_ONLY = {
    "dashboard/<int:event_id>/", "review/<int:event_id>/", "review/attendee/<int:attendee_id>/<str:decision>/",
    "export_delta/<int:event_id>/<int:request_id>/", "export_package/<uuid:package_id>/download/",
    "export_package/<uuid:package_id>/acknowledge/",
    # API проверки, выгрузки и бейджей Next.js (views/staff_api.py, badges_api.py).
    "api/v1/staff/events/", "api/v1/staff/events/<int:event_id>/dashboard/",
    "api/v1/staff/events/<int:event_id>/review/", "api/v1/staff/attendees/<int:attendee_id>/<str:decision>/",
    "api/v1/staff/packages/<uuid:package_id>/execute/", "api/v1/staff/packages/<uuid:package_id>/result-template/",
    "api/v1/events/<int:event_id>/badge-template/", "api/v1/events/<int:event_id>/badge-template/background/",
    "api/v1/events/<int:event_id>/badges/candidates/", "api/v1/events/<int:event_id>/badges/preview/",
    "api/v1/events/<int:event_id>/badges/", "api/v1/events/<int:event_id>/attendees/<int:attendee_id>/badge.pdf",
    "api/v1/jobs/<int:job_id>/", "api/v1/jobs/<int:job_id>/file/",
}
SKIP_PREFIXES = ("embankment/auth", "embankment/axes", "embankment/eventproject", "embankment/directories",
                 "embankment/qr_event", "embankment/r/", "embankment/^", "embankment/(", "embankment/password",
                 "embankment/logout", "embankment/autocomplete", "embankment/jsi18n")


def walk(patterns, prefix=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern)


def routes():
    seen = []
    for pattern in walk(get_resolver().url_patterns):
        if pattern.startswith(SKIP_PREFIXES) or "(?P<format>" in pattern or "<drf_format_suffix" in pattern:
            continue
        if pattern not in seen:
            seen.append(pattern)
    return seen


def base(pattern):
    """Шаблон без языкового префикса: «kz/show/<int:request_id>/» → «show/<int:request_id>/»."""
    return re.sub(r"^(kz|en)/", "", pattern)


@override_settings(RATELIMIT_ENABLE=False, AXES_ENABLED=False)
class AccessMatrixTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media = tempfile.mkdtemp(prefix="access-matrix-")
        cls._media_override = override_settings(MEDIA_ROOT=cls.media)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls.media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        today = date.today()
        self.event_a = Event.objects.create(name_rus="Событие А", title="A", date_start=today, date_end=today + timedelta(days=5))
        self.event_b = Event.objects.create(name_rus="Событие Б", title="B", date_start=today, date_end=today + timedelta(days=5))
        self.users = {}
        self.op_a = self._operator("op_a", "operator", self.event_a)
        self.op_b = self._operator("op_b", "operator", self.event_b)
        self.sup = self._operator("sup_b", "superoperator", self.event_b)
        self.admin = User.objects.create_superuser("admin_m", "admin@example.invalid", "x")
        self.users["admin"] = self.admin
        self.req_a = Request.objects.create(name="RA", event=self.event_a, status="Active", created_by=self.op_a.operator,
                                            registration_time=timezone.now())
        self.photo_rel = f"event_{self.event_a.pk}/matrix_photo.jpg"
        self.att_a = Attendee.objects.create(
            surname=MARKER, firstname="Тест", post="P", countryId="1000000840", is_resident=False,
            docTypeId="1000000002", docSeries="", docNumber="M1", docIssue="", sexId="1", visitObjects="Зал",
            transcription="MARKEROVA TEST", request=self.req_a, dateAdd=timezone.now(), status="submitted",
            birthDate=date(1990, 1, 1), docBegin=date(2020, 1, 1), docEnd=date(2034, 1, 1), photo=self.photo_rel,
        )
        self._ensure_photo()

    def _operator(self, username, role, event):
        user = User.objects.create_user(username, password="x")
        op = Operator.objects.create(user=user, role=role, patronymic="P", phone_number="+7")
        op.events.add(event)
        self.users[username] = user
        return user

    def _ensure_photo(self):
        path = os.path.join(self.media, self.photo_rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "wb") as fh:
                fh.write(b"\xff\xd8\xff\xe0" + MARKER.encode() + b"\xff\xd9")

    def url(self, pattern):
        values = {
            "request_id": self.req_a.pk, "event_id": self.event_a.pk, "attendee_id": self.att_a.pk,
            "operator_id": self.op_a.operator.pk, "username": "op_a", "decision": "start",
            "package_id": str(uuid.uuid4()), "uidb64": "MQ", "token": "bad-token", "file_path": self.photo_rel,
            "field_id": 1, "link_id": 1, "token_id": 1, "job_id": 1,
        }
        b = base(pattern)
        pk = {"api/v1/^attendees": self.att_a.pk, "api/v1/^requests": self.req_a.pk, "api/v1/^events": self.event_a.pk,
              "api/v1/^operators": self.op_a.operator.pk, "qr/success": 1}
        values["pk"] = next((v for k, v in pk.items() if b.startswith(k)), 1)
        # Сначала группы регулярных выражений «(?P<pk>…)», потом конвертеры «<int:pk>».
        path = re.sub(r"\(\?P<(\w+)>[^)]*\)", lambda m: str(values[m.group(1)]), pattern)
        path = re.sub(r"<(?:\w+:)?(\w+)>", lambda m: str(values[m.group(1)]), path)
        path = path.replace("^", "").replace("$", "")
        return "/" + path

    def state(self):
        """Снимок данных мероприятия A и учётных записей — по нему видно любое изменение."""
        att = Attendee.objects.filter(pk=self.att_a.pk).values_list("surname", "status", "post", "review_comment").first()
        req = Request.objects.filter(pk=self.req_a.pk).values_list("status", "name").first()
        return (
            att, req, Attendee.objects.filter(request__event=self.event_a).count(),
            Request.objects.filter(event=self.event_a).count(), Event.objects.count(), Operator.objects.count(),
            tuple(User.objects.order_by("pk").values_list("username", "is_active", "password")),
            tuple(Operator.objects.order_by("pk").values_list("pk", "role")),
            tuple(sorted(Event.objects.filter(operator__user__username="op_a").values_list("pk", flat=True))),
            os.path.exists(os.path.join(self.media, self.photo_rel)),
        )

    def request(self, user, method, url):
        # Ошибки сервера (500) записываются в матрицу, а не обрывают обход.
        self.client = Client(raise_request_exception=False)
        if user is not None:
            self.client.force_login(user)
        cache.clear()
        before = self.state()
        with transaction.atomic():
            sid = transaction.savepoint()
            if method == "GET":
                response = self.client.get(url)
            else:
                response = self.client.post(url, {"csrfmiddlewaretoken": "x", "attendee_id": self.att_a.pk,
                                                  "reason": "x", "username": "op_a", "event_id": self.event_a.pk})
            body = b"".join(response.streaming_content) if getattr(response, "streaming", False) else response.content
            after = self.state()
            transaction.savepoint_rollback(sid)
        self._ensure_photo()
        leaked = MARKER in body.decode("utf-8", "ignore")
        return response.status_code, response.get("Location", ""), leaked, before != after

    def test_access_matrix(self):
        actors = {"anon": None, "op_b": self.users["op_b"], "op_a": self.users["op_a"],
                  "sup_b": self.users["sup_b"], "admin": self.users["admin"]}
        rows, violations = [], []
        for pattern in routes():
            b = base(pattern)
            url = self.url(pattern)
            for actor, user in actors.items():
                for method in ("GET", "POST"):
                    status, location, leaked, changed = self.request(user, method, url)
                    rows.append([pattern, url, actor, method, status, location, int(leaked), int(changed)])
                    ok2xx = 200 <= status < 300
                    if actor == "anon" and b not in PUBLIC and (ok2xx or leaked or changed):
                        violations.append(("anon", method, url, status, leaked, changed))
                    if actor == "op_b" and (leaked or changed):
                        violations.append(("op_b", method, url, status, leaked, changed))
                    if actor == "op_a" and (b in ADMIN_ONLY or b in REVIEW_ONLY) and (ok2xx or changed):
                        violations.append(("op_a", method, url, status, leaked, changed))
                    if actor == "sup_b" and b in ADMIN_ONLY and (ok2xx or changed):
                        violations.append(("sup_b", method, url, status, leaked, changed))
                    # Ни одна роль не должна получать «внутреннюю ошибку» (503 у /qr/ — намеренно
                    # отключённая публичная форма, см. qr_event/views.py).
                    if status >= 500 and not (status == 503 and b.startswith("qr/")):
                        violations.append((actor, method, url, status, "server error"))
        out = os.environ.get("ACCESS_MATRIX_OUT")
        if out:
            with open(out, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["pattern", "url", "actor", "method", "status", "location", "leaked", "changed"])
                writer.writerows(rows)
        self.assertGreater(len(rows), 600)
        owner_ok = {(r[1], r[3]) for r in rows if r[2] == "op_a" and 200 <= r[4] < 300}
        for must in (f"/show/{self.req_a.pk}/", f"/api/v1/attendees/{self.att_a.pk}/", f"/media/{self.photo_rel}",
                     f"/kz/show/{self.req_a.pk}/"):
            self.assertIn((must, "GET"), owner_ok)
        self.assertEqual(violations, [])

    def test_attendee_file_access(self):
        url = f"/media/{self.photo_rel}"
        expected = {"anon": False, "op_b": False, "op_a": True, "admin": True}
        for actor, allowed in expected.items():
            with self.subTest(actor=actor):
                status, _, _, _ = self.request(self.users.get(actor) if actor != "anon" else None, "GET", url)
                self.assertEqual(status == 200, allowed, status)
