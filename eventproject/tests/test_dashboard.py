"""Story 4.2 — тесты дашборда статусов Супероператора."""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from eventproject.models import Attendee, Event, Operator, Request
from eventproject.views.dashboard import _compute_dashboard

KZ = "1000000105"
NON_KZ = "1000000840"


class DashboardBase(TestCase):
    def setUp(self):
        cache.clear()
        self.event = Event.objects.create(name_rus="E1", title="Event 1", event_code="T1")

        self.super_user = User.objects.create_user("super", password="Pass123!")
        Operator.objects.create(
            user=self.super_user, role="superoperator", patronymic="С",
            phone_number="+70000000001", workplace="HQ",
        )
        self.op_user = User.objects.create_user("op", password="Pass123!")
        self.operator = Operator.objects.create(
            user=self.op_user, role="operator", patronymic="О",
            phone_number="+70000000002", workplace="HQ",
        )
        self.req = Request.objects.create(
            name="R", event=self.event, status="Active", created_by=self.operator,
            registration_time=timezone.now(),
        )

    def _mk(self, status, *, is_resident=False, iin=None, photo="img.jpg",
            doc="img.jpg", request=None, **over):
        data = dict(
            surname="Тест", firstname="Имя", post="P",
            countryId=KZ if is_resident else NON_KZ,
            docTypeId="passport", docSeries="AA", docIssue="МВД", sexId="M",
            visitObjects="Зал", transcription="T", request=request or self.req,
            dateAdd=timezone.now(), status=status, is_resident=is_resident,
            iin=iin, photo=photo, docScan=doc,
        )
        data.update(over)
        return Attendee.objects.create(**data)


class DashboardComputeTests(DashboardBase):
    def setUp(self):
        super().setUp()
        self.a_ready = self._mk("ready", is_resident=True, iin="900101300007")
        self.a_draft = self._mk("draft")
        self.a_submitted = self._mk("submitted")
        self.a_in_review = self._mk("in_review")
        self.a_iin = self._mk("submitted", is_resident=True, iin=None, surname="БезИИН")
        self.a_photo = self._mk("draft", photo="", surname="БезФото")
        self.a_doc = self._mk("draft", doc="", surname="БезДок")

    def test_status_counts(self):
        d = _compute_dashboard(self.event)
        self.assertEqual(d["total"], 7)
        self.assertEqual(d["ready"], 1)
        self.assertEqual(d["review"], 3)  # 2 submitted + 1 in_review
        self.assertEqual(d["draft"], 3)
        self.assertFalse(d["all_ready"])

    def test_flag_iin_missing(self):
        flags = {f["key"]: f for f in _compute_dashboard(self.event)["flags"]}
        ids = [i["id"] for i in flags["iin"]["items"]]
        self.assertIn(self.a_iin.id, ids)
        self.assertNotIn(self.a_submitted.id, ids)  # нерезидент без ИИН не флагуется

    def test_flag_photo_missing(self):
        flags = {f["key"]: f for f in _compute_dashboard(self.event)["flags"]}
        ids = [i["id"] for i in flags["photo"]["items"]]
        self.assertEqual(ids, [self.a_photo.id])

    def test_flag_doc_missing(self):
        flags = {f["key"]: f for f in _compute_dashboard(self.event)["flags"]}
        ids = [i["id"] for i in flags["doc"]["items"]]
        self.assertEqual(ids, [self.a_doc.id])


class DashboardViewTests(DashboardBase):
    def _url(self):
        return f"/dashboard/{self.event.id}/"

    def test_anonymous_redirected(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 302)

    def test_operator_forbidden(self):
        self.client.force_login(self.op_user)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 302)  # user_passes_test → редирект на логин

    def test_superoperator_access(self):
        self._mk("ready", is_resident=True, iin="900101300007")
        self.client.force_login(self.super_user)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)

    def test_flag_name_links_to_edit(self):
        a = self._mk("submitted", is_resident=True, iin=None, surname="Флагов")
        self.client.force_login(self.super_user)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f"/update_attendee/{a.id}/")  # имя кликабельно → редактирование
        self.assertContains(resp, "Флагов")

    def test_all_ready_message(self):
        self._mk("ready", is_resident=True, iin="900101300007")
        self._mk("ready", is_resident=True, iin="900101300007")
        self.client.force_login(self.super_user)
        resp = self.client.get(self._url())
        self.assertContains(resp, "готовы к экспорту")

    def test_missing_event_404(self):
        self.client.force_login(self.super_user)
        resp = self.client.get("/dashboard/999999/")
        self.assertEqual(resp.status_code, 404)
