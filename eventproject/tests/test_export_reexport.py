"""Story hd-1.3 — re-export как явное подтверждённое действие (FR-3).

Молчаливый re-export жил в двух местах file_download.py:
- download_request_json — отдавал заявку по id без проверки статуса и безусловно
  помечал Exported (маркер hd-1.2 «Q2 → hd-1-3»);
- download_all_guests_json — полный дамп Sent+Exported (hd-1.2 Q1).

Контракт hd-1.3: путь, который повторно выгружает уже-Exported заявку, требует
POST-параметр `confirm_reexport` — без него 409 (ничего не выгружено, не помечено,
не зааудировано), с ним — прежний whitelist-payload + durable-аудит
`export.re_export`. Обычный экспорт (Sent-only) не меняется. Set-эндпоинты
download_json/download_guests_json игнорируют Exported (AC-1 pin).
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from directories.models import Country, DocumentType, Sex
from eventproject.models import AuditLog, Event, Request
from eventproject.serializers.export import (
    LEGACY_EVENT_FIELDS,
    LEGACY_REQUEST_FIELDS,
)
from eventproject.tests.test_attendee_api import (
    KZ,
    _make_attendee,
    _make_operator,
)
from eventproject.tests.test_export_whitelist import IIN_PATTERN

PASSWORD = "StrongPass123!"
CONFIRM = {"confirm_reexport": "1"}


class ReExportBase(TestCase):
    """Событие с одной Sent- и одной Exported-заявкой (по участнику в каждой)."""

    def setUp(self):
        Country.objects.create(
            country_code=KZ, name_rus="Казахстан", name_kaz="", name_eng="",
            country_iso="KZ",
        )
        Sex.objects.create(sex_code="M", name_rus="Мужской", name_kaz="", name_eng="")
        DocumentType.objects.create(
            doc_code="ID", name_rus="Удостоверение", name_kaz="", name_eng=""
        )
        self.superuser = User.objects.create_superuser(
            username="su", password=PASSWORD, email=""
        )
        _, self.operator = _make_operator("oper", "operator")
        self.event = Event.objects.create(
            name_rus="Событие", event_code="REX1", city_code="ALA"
        )
        self.sent_req = Request.objects.create(
            name="Отправленная", event=self.event, status="Sent",
            created_by=self.operator, registration_time=timezone.now(),
        )
        # Exported-состояние в фикстурах проекта создаётся напрямую
        # (нигде иначе не создаётся — см. story Dev Notes).
        self.exported_req = Request.objects.create(
            name="Выгруженная", event=self.event, status="Exported",
            created_by=self.operator, registration_time=timezone.now(),
        )
        self.sent_attendee = _make_attendee(
            self.sent_req, status="ready", surname="Сентов"
        )
        self.exported_attendee = _make_attendee(
            self.exported_req, status="exported", surname="Экспортов"
        )
        self.client.force_login(self.superuser)

    def _audit_count(self, action, **extra_filter):
        return AuditLog.objects.filter(action=action, **extra_filter).count()

    def _assert_no_iin(self, resp):
        body = resp.content.decode("utf-8")
        self.assertNotRegex(body, IIN_PATTERN)
        return body


class RequestJsonReExportTests(ReExportBase):
    """AC-2: /download_request_json/ — confirm-gate на уже-Exported заявке."""

    def _url(self, req):
        return f"/download_request_json/{req.id}/"

    def test_exported_without_confirm_is_409_and_silent(self):
        resp = self.client.post(self._url(self.exported_req))
        self.assertEqual(resp.status_code, 409)
        self.exported_req.refresh_from_db()
        self.assertEqual(self.exported_req.status, "Exported")
        self.assertEqual(self._audit_count("export.re_export"), 0)
        self.assertEqual(self._audit_count("export.request"), 0)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_exported_with_confirm_re_exports_and_audits_re_export(self):
        resp = self.client.post(self._url(self.exported_req), CONFIRM)
        self.assertEqual(resp.status_code, 200)
        body = self._assert_no_iin(resp)
        payload = json.loads(body)
        # Прежний whitelist-payload (hd-1.1) — wire-формат не меняется.
        self.assertEqual(
            set(payload.keys()), LEGACY_REQUEST_FIELDS | {"attendees", "event"}
        )
        self.assertEqual(set(payload["event"].keys()), LEGACY_EVENT_FIELDS)
        self.assertIn("Экспортов", body)
        self.exported_req.refresh_from_db()
        self.assertEqual(self.exported_req.status, "Exported")
        # Одно действие = одна durable-строка: re_export ВМЕСТО request.
        self.assertEqual(self._audit_count("export.request"), 0)
        rows = AuditLog.objects.filter(action="export.re_export")
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.obj_type, "Request")
        self.assertEqual(row.obj_id, str(self.exported_req.id))
        self.assertEqual(row.actor_id, self.superuser.id)
        self.assertEqual(row.extra.get("attendees"), 1)
        self.assertEqual(row.extra.get("event_id"), self.event.id)

    def test_sent_without_confirm_is_normal_export(self):
        resp = self.client.post(self._url(self.sent_req))
        self.assertEqual(resp.status_code, 200)
        self._assert_no_iin(resp)
        self.sent_req.refresh_from_db()
        self.assertEqual(self.sent_req.status, "Exported")
        self.assertEqual(self._audit_count("export.request"), 1)
        self.assertEqual(self._audit_count("export.re_export"), 0)

    def test_sent_with_confirm_param_is_still_normal_export(self):
        # Лишний confirm на Sent не превращает первый экспорт в re-export.
        resp = self.client.post(self._url(self.sent_req), CONFIRM)
        self.assertEqual(resp.status_code, 200)
        self.sent_req.refresh_from_db()
        self.assertEqual(self.sent_req.status, "Exported")
        self.assertEqual(self._audit_count("export.request"), 1)
        self.assertEqual(self._audit_count("export.re_export"), 0)

    def test_non_one_confirm_values_do_not_pass_the_gate(self):
        # Ревью hd-1.3: подтверждение = ровно "1" (как шлёт UI), не truthy —
        # confirm_reexport=0/false/мусор от программного клиента → 409.
        for bad in ("0", "false", "no", "yes", "true", " 1"):
            with self.subTest(value=bad):
                resp = self.client.post(
                    self._url(self.exported_req), {"confirm_reexport": bad}
                )
                self.assertEqual(resp.status_code, 409)
        self.assertEqual(AuditLog.objects.count(), 0)


class AllGuestsReExportTests(ReExportBase):
    """AC-3: /download_all_guests_json/ — confirm-gate при Exported в наборе."""

    def _url(self):
        return f"/download_all_guests_json/{self.event.id}/"

    def test_mixed_set_without_confirm_is_409_and_nothing_marked(self):
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 409)
        self.sent_req.refresh_from_db()
        # Sent НЕ помечена — 409 до любых мутаций.
        self.assertEqual(self.sent_req.status, "Sent")
        self.assertEqual(self._audit_count("export.guests_all"), 0)
        self.assertEqual(self._audit_count("export.re_export"), 0)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_mixed_set_with_confirm_dumps_all_and_audits_both(self):
        resp = self.client.post(self._url(), CONFIRM)
        self.assertEqual(resp.status_code, 200)
        body = self._assert_no_iin(resp)
        # Семантика полного дампа сохранена: оба участника в payload.
        self.assertIn("Сентов", body)
        self.assertIn("Экспортов", body)
        self.sent_req.refresh_from_db()
        self.assertEqual(self.sent_req.status, "Exported")
        # Роут-action как раньше + отдельная строка re_export за подгруппу.
        self.assertEqual(self._audit_count("export.guests_all"), 1)
        rows = AuditLog.objects.filter(action="export.re_export")
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.obj_type, "Event")
        self.assertEqual(row.obj_id, str(self.event.id))
        self.assertEqual(
            row.extra.get("re_exported_request_ids"), [self.exported_req.id]
        )
        self.assertEqual(row.extra.get("re_exported_count"), 1)

    def test_sent_only_set_without_confirm_unchanged(self):
        # Чисто-Sent набор = обычный экспорт: подтверждение НЕ требуется.
        self.exported_req.delete()
        resp = self.client.post(self._url())
        self.assertEqual(resp.status_code, 200)
        self.sent_req.refresh_from_db()
        self.assertEqual(self.sent_req.status, "Exported")
        self.assertEqual(self._audit_count("export.guests_all"), 1)
        self.assertEqual(self._audit_count("export.re_export"), 0)

    def test_non_one_confirm_value_does_not_pass_the_gate(self):
        # Ревью hd-1.3: ровно "1", не truthy (зеркало request_json-кейса).
        resp = self.client.post(self._url(), {"confirm_reexport": "0"})
        self.assertEqual(resp.status_code, 409)
        self.sent_req.refresh_from_db()
        self.assertEqual(self.sent_req.status, "Sent")
        self.assertEqual(AuditLog.objects.count(), 0)


class NormalExportIgnoresExportedTests(ReExportBase):
    """AC-1 pin: Sent-only set-эндпоинты не трогают Exported-заявку."""

    def _assert_exported_ignored(self, url):
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        body = self._assert_no_iin(resp)
        self.assertIn("Сентов", body)
        self.assertNotIn("Экспортов", body)
        self.exported_req.refresh_from_db()
        self.assertEqual(self.exported_req.status, "Exported")
        self.assertEqual(self._audit_count("export.re_export"), 0)

    def test_download_json_ignores_exported(self):
        self._assert_exported_ignored(f"/download_json/{self.event.id}/")

    def test_download_guests_json_ignores_exported(self):
        self._assert_exported_ignored(f"/download_guests_json/{self.event.id}/")


class ShowEventReExportUiTests(ReExportBase):
    """AC-5 (тестируемый срез): формы event.html несут confirm_reexport.

    Браузерный confirm()-диалог = manual QA; здесь пин серверного рендера:
    hidden-параметр появляется ровно там, где действие = re-export.
    """

    def _page(self):
        resp = self.client.get(f"/show_event/{self.event.id}/")
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode("utf-8")

    def test_page_with_exported_requests_renders_confirm_param(self):
        body = self._page()
        # Форма полного дампа + per-row форма Exported-заявки (ровно 2 вхождения).
        self.assertEqual(body.count('name="confirm_reexport"'), 2)

    def test_page_without_exported_requests_has_no_confirm_param(self):
        self.exported_req.delete()
        body = self._page()
        self.assertNotIn("confirm_reexport", body)
