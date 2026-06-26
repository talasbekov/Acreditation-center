"""Story hd-7.1 — bypass-пути в обход обычных DRF-вьюсетов (AC-3).

Два не-DRF канала доступа к данным/PII:
  • media-serve (`protected_media`, `/media/event_<id>/…`) — фото/документы/биометрия;
  • QR-поток (`/qr/success/<pk>/`).

protected_media — РЕАЛЬНО event-scoped (regex `event_<id>/` + `operator.events`),
поэтому здесь полноценные негативы (#23–25 из P0-перечисления). QR — слабый
скоуп (session/superuser, БЕЗ event-scope) и ОТСУТСТВИЕ entrance/scan-валидации:
фиксируем тестами-маркерами + defer (см. rbac_matrix.KNOWN_GAPS / docs/rbac-matrix.md).
Рантайм НЕ меняем.
"""
import os
import shutil
import tempfile

from django.test import Client, override_settings
from django.urls import reverse

from eventproject.models import Request
from eventproject.tests.rbac_matrix import MEDIA_CELLS
from eventproject.tests.test_rbac_matrix import RBACMatrixBase
from qr_event.models import QrIin
from qr_event.views import SESSION_QR_PKS


class MediaBypassTests(RBACMatrixBase):
    """#23–25: оператор листа A не получает файлы event_{B|P|C}/ → 404; own → 200."""

    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp(prefix="hd71_media_")
        ovr = override_settings(MEDIA_ROOT=self.media_root)
        ovr.enable()
        self.addCleanup(ovr.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        # Реальные файлы для всех событий (own-позитив требует isfile()).
        for ev in (self.A, self.B, self.P, self.C):
            directory = os.path.join(self.media_root, f"event_{ev.id}")
            os.makedirs(directory, exist_ok=True)
            with open(os.path.join(directory, "probe.txt"), "wb") as fh:
                fh.write(b"pii-bytes")

        self._media_event = {
            "own": self.A, "sibling": self.B, "parent": self.P, "foreign_tree": self.C,
        }
        self.media_client = Client()
        self.media_client.force_login(self.opA_user)

    def _get_media(self, event, client=None):
        return (client or self.media_client).get(f"/media/event_{event.id}/probe.txt")

    def test_media_superuser_bypasses_event_scope(self):
        # Суперпользователь — без event-ограничений (документированное поведение).
        su_client = Client()
        su_client.force_login(self.su_user)
        self.assertEqual(self._get_media(self.B, su_client).status_code, 200)

    def test_media_anonymous_redirected_to_login(self):
        self.assertEqual(self._get_media(self.A, Client()).status_code, 302)

    def test_media_path_traversal_blocked(self):
        # Defense-in-depth: ../ за пределы MEDIA_ROOT → 404 (не leak вне каталога).
        self.assertEqual(
            self.media_client.get("/media/event_%d/../../etc/passwd" % self.A.id).status_code,
            404,
        )

    def test_media_within_root_traversal_to_foreign_event_blocked(self):
        # CRITICAL-регрессия (code-review hd-7.1): within-root traversal
        # event_{A}/../event_{B}/ резолвится в event_{B} (внутри MEDIA_ROOT →
        # commonpath пропускает). Авторизация по РЕЗОЛВНУТОМУ пути → 404, а не leak
        # файла чужого листа. До фикса (id из сырого file_path) отдавался 200.
        resp = self.media_client.get(
            "/media/event_%d/../event_%d/probe.txt" % (self.A.id, self.B.id)
        )
        self.assertEqual(resp.status_code, 404)


class QrBypassPathTests(RBACMatrixBase):
    """QR-скоуп: слабый (session/superuser, без event-scope) + нет entrance-валидации."""

    def setUp(self):
        super().setUp()
        # iin валиден по KZ-checksum (как Attendee VALID_IIN); ORM-create не валидирует.
        self.qr = QrIin.objects.create(iin="851205301234")

    def test_qr_success_operator_not_creator_redirected(self):
        # Оператор A (есть события!) НЕ создатель записи в сессии → отказ (deny-redirect
        # на iin_form, НЕ login-redirect). Проверяем цель: QR-скоуп session-based, НЕ
        # event-based (gap, defer → QR-история).
        client = Client()
        client.force_login(self.opA_user)
        resp = client.get(f"/qr/success/{self.qr.pk}/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("iin_form"))  # deny-redirect, не /user_login/

    def test_qr_success_anonymous_redirected_to_login(self):
        resp = Client().get(f"/qr/success/{self.qr.pk}/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(  # login_required, НЕ deny-redirect на iin_form
            resp.url.startswith("/user_login/"), f"ожидался login-redirect, получен {resp.url}"
        )

    def test_qr_success_session_creator_bypasses_without_event_scope(self):
        # Маркер gap: членство в session-списке (а НЕ владение событием) даёт доступ.
        client = Client()
        client.force_login(self.opA_user)
        session = client.session
        session[SESSION_QR_PKS] = [self.qr.pk]
        session.save()
        resp = client.get(f"/qr/success/{self.qr.pk}/")
        # Доступ выдан по сессии (без event-scope) → 200, НЕ redirect. assertEqual(200),
        # а не assertNotEqual(302): иначе любой 4xx/5xx ложно «доказал» бы доступ.
        self.assertEqual(resp.status_code, 200)

    def test_qr_entrance_validation_endpoint_absent(self):
        """Маркер-defer: entrance/scan-валидации (сверка ИИН на входе) НЕТ.

        Не выдумываем эндпоинт — фиксируем факт: в qr_event только форма генерации
        (iin_form) и страница успеха (qr_success). Появится в новой QR-истории.
        """
        from qr_event import urls as qr_urls

        # Только форма генерации (iin_form) и страница успеха (qr_success); никакого
        # entrance/scan-эндпоинта. assertEqual фиксирует ТОЧНЫЙ набор имён (entrance в
        # т.ч.) — отдельный assertNotIn("entrance") был бы мёртвым (набор уже закреплён).
        names = {p.name for p in qr_urls.urlpatterns}
        self.assertEqual(names, {"iin_form", "qr_success"})


# ── динамическая генерация media-негативов (#23–25) + own-позитив из oracle ──
def _make_media_test(cell):
    def test(self):
        event = self._media_event[cell["target"]]
        resp = self._get_media(event)
        self._assert_outcome(
            cell["expected"], resp, msg=f"media #{cell.get('n')} {cell['target']}"
        )

    test.__doc__ = f"media event_{{{cell['target']}}} → {cell['expected']}"
    return test


for _cell in MEDIA_CELLS:
    _suffix = ("%02d_%s" % (_cell["n"], _cell["target"])) if _cell["n"] else ("own_%s" % _cell["target"])
    setattr(MediaBypassTests, "test_media_%s" % _suffix, _make_media_test(_cell))


class LegacyFormViewOwnershipTests(RBACMatrixBase):
    """AC-1: legacy form-views (`@login_required` + ownership по `req.created_by`).

    Не DRF-вьюсеты: изоляция — проверкой `req.created_by != operator` в самом view
    (`views/request.py:97`). Слабее DRF (при отказе отдаётся 200-текст, не 403/404 —
    зафиксировано как факт-маркер). Покрываем ownership-кейс (минимум по spec-инвентарю);
    полная зачистка legacy-форм-вьюсетов — out-of-scope hd-7.1.
    """

    def test_delete_request_foreign_owner_denied(self):
        # Оператор C (НЕ создатель reqA) не может удалить чужую заявку: отказ +
        # объект НЕ удалён. Доказывает ownership-enforcement (хоть и 200-текстом).
        client = Client(enforce_csrf_checks=False)
        client.force_login(self.opC_user)
        resp = client.post(reverse("delete_request", args=[self.reqA.id]))
        self.assertContains(resp, "not authorised")  # legacy-отказ: 200-текст, не 403
        self.assertTrue(Request.objects.filter(pk=self.reqA.id).exists())  # НЕ удалена

    def test_delete_request_own_owner_allowed(self):
        # Позитив (анти-over-block): создатель удаляет СВОЮ заявку → redirect + удалена.
        # Свежая заявка без участников — чтобы delete не зависел от cascade на Attendee.
        from eventproject.tests.test_attendee_api import _make_request

        own_req = _make_request(self.A, self.opA)
        client = Client(enforce_csrf_checks=False)
        client.force_login(self.opA_user)
        resp = client.post(reverse("delete_request", args=[own_req.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Request.objects.filter(pk=own_req.id).exists())  # удалена
