"""Story hd-4.2 — чек-лист покрытия значимых действий (SIGNIFICANT_ACTIONS).

AC-1: реестр eventproject/audit.py::SIGNIFICANT_ACTIONS — единственный источник
правды для этого чек-листа. Для каждого перечисленного action здесь есть тест,
реально вызывающий живой view через self.client и подтверждающий аудит-строку
через assertLogs("eventproject") (паттерн
test_operator_onboarding.py::test_create_emits_audit_log).

Мульти-роутные action покрыты ПО-РОУТНО (AC-1, And-клауза): user.login — RU/KZ/EN
(три разных view-функции), event.delete — legacy/flush/DRF, request.delete —
RU/KZ/EN, attendee.delete — DRF/RU/KZ/EN (code review hd-4.2), attendee.update —
DRF/RU-legacy (code review hd-4.2). Анти-дрейф: ACTION_COVERAGE ↔ реестр
(set-equality) + существование каждого тест-метода — новый action в реестре без
чек-лист-теста валит мета-тест.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from directories.models import Country, DocumentType, Sex
from eventproject.audit import SIGNIFICANT_ACTIONS
from eventproject.models import Attendee, AuditLog, Event, Request
from eventproject.tests.test_attendee_api import (
    BDATE,
    KZ,
    OTHER,
    VALID_IIN,
    _make_attendee,
    _make_operator,
    _make_request,
)

PASSWORD = "StrongPass123!"

# Карта покрытия: action → тесты этого модуля, реально бьющие по живому view.
# Мульти-роутные action перечисляют тест НА КАЖДЫЙ живой роут (AC-1, And-клауза).
ACTION_COVERAGE = {
    "user.login": [
        "LoginAuditTests.test_ru_login_superuser_without_operator_is_audited",
        "LoginAuditTests.test_kz_login_is_audited",
        "LoginAuditTests.test_en_login_is_audited",
    ],
    "user.change_password": [
        "ChangePasswordAuditTests."
        "test_ru_change_password_superuser_without_operator_is_audited",
    ],
    "attendee.status_change": [
        "AttendeeStatusChangeAuditTests.test_submit_emits_attendee_status_change",
    ],
    "attendee.approved": [
        "AttendeeStatusChangeAuditTests.test_approve_emits_attendee_approved",
    ],
    "attendee.returned": [
        "AttendeeStatusChangeAuditTests.test_return_emits_attendee_returned",
    ],
    "attendee.update": [
        "AttendeeEditAuditTests.test_update_emits_attendee_update",
        "AttendeeEditAuditTests.test_legacy_ru_update_attendee_emits_attendee_update",
    ],
    "attendee.iin_discarded": [
        "AttendeeEditAuditTests.test_residency_change_emits_attendee_iin_discarded",
    ],
    "attendee.delete": [
        "AttendeeDeleteAuditTests.test_destroy_emits_attendee_delete",
        "AttendeeDeleteAuditTests.test_legacy_ru_delete_attendee_emits_attendee_delete",
        "AttendeeDeleteAuditTests.test_kz_delete_attendee_emits_attendee_delete",
        "AttendeeDeleteAuditTests.test_en_delete_attendee_emits_attendee_delete",
    ],
    "export.download": [
        "ExportDeltaAuditTests.test_export_delta_emits_export_download",
    ],
    "export.event_sent": [
        "LegacyExportEndpointsAuditTests.test_download_json_emits_export_event_sent",
    ],
    "export.guests_sent": [
        "LegacyExportEndpointsAuditTests."
        "test_download_guests_json_emits_export_guests_sent",
    ],
    "export.guests_all": [
        "LegacyExportEndpointsAuditTests."
        "test_download_all_guests_json_emits_export_guests_all",
    ],
    "export.request": [
        "LegacyExportEndpointsAuditTests."
        "test_download_request_json_emits_export_request",
    ],
    "export.re_export": [
        "ReExportAuditTests.test_request_json_reexport_confirmed_emits_re_export",
        "ReExportAuditTests.test_all_guests_reexport_confirmed_emits_re_export",
    ],
    "event.delete": [
        "EventDeleteAuditTests.test_legacy_delete_event_is_audited",
        "EventDeleteAuditTests.test_flush_outdated_events_audits_each_deleted_event",
        "EventDeleteAuditTests.test_drf_event_destroy_is_audited",
    ],
    "request.delete": [
        "RequestDeleteAuditTests.test_ru_delete_request_is_audited",
        "RequestDeleteAuditTests.test_kz_delete_request_is_audited",
        "RequestDeleteAuditTests.test_en_delete_request_is_audited",
    ],
}


def _flat_registry_actions():
    return {a for actions in SIGNIFICANT_ACTIONS.values() for a in actions}


class AuditChecklistMixin:
    """Общий приём чек-листа: вызвать view, собрать action'ы из лог-записей."""

    def _actions_of(self, cm):
        return [getattr(r, "action", None) for r in cm.records]

    def _records_for(self, cm, action):
        return [r for r in cm.records if getattr(r, "action", None) == action]


class SignificantActionsRegistryTests(TestCase):
    """AC-1: мета-тесты реестра."""

    def test_registry_has_exactly_expected_categories(self):
        self.assertEqual(
            set(SIGNIFICANT_ACTIONS),
            {"login", "status_change", "edit", "export", "export.re_export", "delete"},
        )

    def test_no_intentionally_empty_categories(self):
        # Анти-регрессия AC-1: hd-1.3 наполнила export.re_export — пустых категорий
        # в реестре больше НЕТ. Если кто-то случайно опустошит категорию — падает.
        self.assertEqual(
            {k: v for k, v in SIGNIFICANT_ACTIONS.items() if not v},
            {},
        )

    def test_every_registry_action_has_explicit_checklist_test(self):
        # Анти-дрейф: реестр ↔ карта покрытия (set-equality) + каждый заявленный
        # тест-метод реально существует в этом модуле.
        self.assertEqual(set(ACTION_COVERAGE), _flat_registry_actions())
        for action, test_ids in ACTION_COVERAGE.items():
            self.assertTrue(test_ids, f"нет чек-лист-тестов для {action}")
            for test_id in test_ids:
                cls_name, method_name = test_id.split(".")
                cls = globals().get(cls_name)
                self.assertIsNotNone(cls, f"{test_id}: класс не найден ({action})")
                self.assertTrue(
                    callable(getattr(cls, method_name, None)),
                    f"{test_id} не существует (покрытие {action})",
                )


class LoginAuditTests(AuditChecklistMixin, TestCase):
    """AC-2: вход аудируется для всех ролей и всех языковых веток (RU/KZ/EN)."""

    def setUp(self):
        # Суперпользователь БЕЗ Operator-профиля — чинимая дыра RU-ветки
        # (audit_log был под `if operator is not None:`); для KZ/EN дыра шире —
        # аудита не было ни для кого.
        self.root = User.objects.create_superuser(
            username="root", password=PASSWORD, email=""
        )

    def _assert_login_audited(self, url):
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(url, {"username": "root", "password": PASSWORD})
        self.assertEqual(resp.status_code, 302)  # успешный вход → redirect
        self.assertIn("user.login", self._actions_of(cm))

    def test_ru_login_superuser_without_operator_is_audited(self):
        self._assert_login_audited("/user_login/")
        # Durable-путь (hd-4.1) идёт тем же вызовом — подтверждаем DB-строку.
        self.assertTrue(
            AuditLog.objects.filter(
                action="user.login", actor_id=self.root.id
            ).exists()
        )

    def test_kz_login_is_audited(self):
        self._assert_login_audited("/kz/user_login/")

    def test_en_login_is_audited(self):
        self._assert_login_audited("/en/user_login/")


class ChangePasswordAuditTests(AuditChecklistMixin, TestCase):
    """AC-3: смена пароля аудируется независимо от Operator-профиля (RU)."""

    def test_ru_change_password_superuser_without_operator_is_audited(self):
        root = User.objects.create_superuser(
            username="root", password=PASSWORD, email=""
        )
        self.client.force_login(root)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(
                "/change_password/",
                {
                    "old_password": PASSWORD,
                    "new_password": "Another123!",
                    "new_password_repeat": "Another123!",
                },
            )
        self.assertEqual(resp.status_code, 200)
        root.refresh_from_db()
        self.assertTrue(root.check_password("Another123!"))  # смена реально прошла
        self.assertIn("user.change_password", self._actions_of(cm))


class AttendeeActionsAuditBase(AuditChecklistMixin, TestCase):
    def setUp(self):
        # BE-5: нерезидентная страна должна существовать в справочнике.
        Country.objects.create(
            country_code=OTHER, name_rus="Иномания", name_kaz="Ino",
            name_eng="Ino", country_iso="IN",
        )
        self.event = Event.objects.create(name_rus="E1", title="Event 1")
        self.su_user, self.su = _make_operator("supero", "superoperator")
        self.op_user, self.op = _make_operator("oper", "operator", event=self.event)
        self.request1 = _make_request(self.event, self.op)
        self.client = APIClient()


class AttendeeStatusChangeAuditTests(AttendeeActionsAuditBase):
    def test_submit_emits_attendee_status_change(self):
        attendee = _make_attendee(self.request1)  # draft, валидный ИИН
        self.client.force_authenticate(self.op_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(f"/api/v1/attendees/{attendee.id}/submit/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attendee.status_change", self._actions_of(cm))

    def test_approve_emits_attendee_approved(self):
        attendee = _make_attendee(self.request1, status="in_review")
        self.client.force_authenticate(self.su_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(f"/api/v1/attendees/{attendee.id}/approve/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attendee.approved", self._actions_of(cm))

    def test_return_emits_attendee_returned(self):
        attendee = _make_attendee(self.request1, status="in_review")
        self.client.force_authenticate(self.su_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(
                f"/api/v1/attendees/{attendee.id}/return/",
                {"reason": "Нечитаемый скан"},
                format="json",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attendee.returned", self._actions_of(cm))


class AttendeeEditAuditTests(AttendeeActionsAuditBase):
    def test_update_emits_attendee_update(self):
        attendee = _make_attendee(self.request1)  # draft — редактируемый
        self.client.force_authenticate(self.op_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.patch(
                f"/api/v1/attendees/{attendee.id}/",
                {"surname": "Новая"},
                format="json",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attendee.update", self._actions_of(cm))

    def test_residency_change_emits_attendee_iin_discarded(self):
        # AC-3: сброс ранее сохранённого ИИН при смене резидентности RK→не-RK.
        # Существующий mock-тест (test_attendee_api.py::
        # test_iin_discard_on_residency_change_is_audited) проверяет call-kwargs
        # через patch; здесь — единообразный assertLogs-чек-лист без моков.
        attendee = _make_attendee(self.request1)  # draft, ИИН сохранён
        self.client.force_authenticate(self.op_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.patch(
                f"/api/v1/attendees/{attendee.id}/",
                {"countryId": OTHER, "iin": ""},
                format="json",
            )
        self.assertEqual(resp.status_code, 200)
        attendee.refresh_from_db()
        self.assertIsNone(attendee.iin)
        self.assertIn("attendee.iin_discarded", self._actions_of(cm))

    def test_legacy_ru_update_attendee_emits_attendee_update(self):
        # AC-1 And-клауза (code review hd-4.2): attendee.update живёт и на
        # легаси-роуте /update_attendee/<id>/ (attendee.py), не только DRF PATCH.
        attendee = _make_attendee(self.request1)
        self.client.force_login(self.op_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(
                f"/update_attendee/{attendee.id}/",
                {
                    # _csrf_missing — ручная проверка наличия токена в POST.
                    "csrfmiddlewaretoken": "x",
                    "last_name": "Легаси",
                    "first_name": "Тест",
                    "iin": VALID_IIN,
                    "dob": BDATE.isoformat(),
                    "sex": "M",
                    "citizenship": KZ,
                    "document_type": "ID",
                    # docBegin/docEnd — DateField: legacy-view пишет POST-строку
                    # как есть, "" в DateField роняет save().
                    "doc_date_start": "2020-01-01",
                    "doc_date_end": "2030-01-01",
                },
            )
        # Успех легаси-view — redirect на /show/<req.id>/ (error → 200 render).
        self.assertEqual(resp.status_code, 302)
        attendee.refresh_from_db()
        self.assertEqual(attendee.surname, "Легаси")
        self.assertIn("attendee.update", self._actions_of(cm))


class AttendeeDeleteAuditTests(AttendeeActionsAuditBase):
    def test_destroy_emits_attendee_delete(self):
        attendee = _make_attendee(self.request1)  # draft — удаляемый оператором
        self.client.force_authenticate(self.op_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.delete(f"/api/v1/attendees/{attendee.id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertIn("attendee.delete", self._actions_of(cm))

    # AC-1 And-клауза (code review hd-4.2): attendee.delete достижим с 4 живых
    # роутов — DRF (выше) + легаси RU /delete_attendee/, /kz/, /en/ — по-роутно.

    def _assert_legacy_delete_audited(self, url):
        attendee = _make_attendee(self.request1)
        self.client.force_login(self.op_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(url, {"attendee_id": attendee.id})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Attendee.objects.filter(id=attendee.id).exists())
        self.assertIn("attendee.delete", self._actions_of(cm))

    def test_legacy_ru_delete_attendee_emits_attendee_delete(self):
        self._assert_legacy_delete_audited("/delete_attendee/")

    def test_kz_delete_attendee_emits_attendee_delete(self):
        self._assert_legacy_delete_audited("/kz/delete_attendee/")

    def test_en_delete_attendee_emits_attendee_delete(self):
        self._assert_legacy_delete_audited("/en/delete_attendee/")


class ExportDeltaAuditTests(AuditChecklistMixin, TestCase):
    """`export.download` — POST /export_delta/ (Integration Spec v1.0 путь)."""

    def setUp(self):
        Country.objects.create(
            country_code=KZ, name_rus="Казахстан", name_kaz="", name_eng="",
            country_iso="KZ",
        )
        Sex.objects.create(sex_code="M", name_rus="Мужской", name_kaz="", name_eng="")
        DocumentType.objects.create(
            doc_code="passport", name_rus="Паспорт", name_kaz="", name_eng=""
        )
        self.event = Event.objects.create(
            name_rus="E1", title="Event 1", event_code="T1"
        )
        self.su_user, _ = _make_operator("supero", "superoperator")
        _, operator = _make_operator("oper", "operator")
        self.category = Request.objects.create(
            name="Охрана", event=self.event, status="Sent", created_by=operator,
            registration_time=timezone.now(),
        )

    def test_export_delta_emits_export_download(self):
        _make_attendee(
            self.category, status="ready", docTypeId="passport",
            photo="img.jpg", docScan="img.jpg",
        )
        self.client.force_login(self.su_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(
                f"/export_delta/{self.event.id}/{self.category.id}/"
            )
        self.assertEqual(resp.status_code, 200)
        b"".join(resp.streaming_content)  # дренируем поток (unlink tmp-файла)
        self.assertIn("export.download", self._actions_of(cm))


class LegacyExportEndpointsAuditTests(AuditChecklistMixin, TestCase):
    """4 живых легаси-JSON-эндпоинта file_download.py (hd-1.1 whitelist-путь)."""

    def setUp(self):
        Country.objects.create(
            country_code=KZ, name_rus="Казахстан", name_kaz="", name_eng="",
            country_iso="KZ",
        )
        Sex.objects.create(sex_code="M", name_rus="Мужской", name_kaz="", name_eng="")
        DocumentType.objects.create(
            doc_code="passport", name_rus="Паспорт", name_kaz="", name_eng=""
        )
        self.superuser = User.objects.create_superuser(
            username="su", password=PASSWORD, email=""
        )
        _, operator = _make_operator("oper2", "operator")
        self.event = Event.objects.create(
            name_rus="Событие", event_code="EXP03", city_code="ALA"
        )
        self.request_obj = Request.objects.create(
            name="Охрана", event=self.event, status="Sent", created_by=operator,
            registration_time=timezone.now(),
        )
        self.attendee = _make_attendee(self.request_obj, status="ready")
        self.client.force_login(self.superuser)

    def _assert_audited(self, url, action):
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(action, self._actions_of(cm))

    def test_download_json_emits_export_event_sent(self):
        self._assert_audited(f"/download_json/{self.event.id}/", "export.event_sent")

    def test_download_guests_json_emits_export_guests_sent(self):
        self._assert_audited(
            f"/download_guests_json/{self.event.id}/", "export.guests_sent"
        )

    def test_download_all_guests_json_emits_export_guests_all(self):
        self._assert_audited(
            f"/download_all_guests_json/{self.event.id}/", "export.guests_all"
        )

    def test_download_request_json_emits_export_request(self):
        self._assert_audited(
            f"/download_request_json/{self.request_obj.id}/", "export.request"
        )


class ReExportAuditTests(AuditChecklistMixin, TestCase):
    """`export.re_export` (hd-1.3, FR-3) — подтверждённый re-export по обоим роутам.

    Поведенческий контракт (409-gate, payload, durable-строки) —
    test_export_reexport.py; здесь чек-лист-минимум: live-роут с confirm
    эмитит export.re_export.
    """

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
            username="su_rex", password=PASSWORD, email=""
        )
        _, operator = _make_operator("oper_rex", "operator")
        self.event = Event.objects.create(
            name_rus="Событие", event_code="REX02", city_code="ALA"
        )
        self.exported_req = Request.objects.create(
            name="Выгруженная", event=self.event, status="Exported",
            created_by=operator, registration_time=timezone.now(),
        )
        _make_attendee(self.exported_req, status="exported")
        self.client.force_login(self.superuser)

    def _assert_reexport_audited(self, url):
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(url, {"confirm_reexport": "1"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("export.re_export", self._actions_of(cm))

    def test_request_json_reexport_confirmed_emits_re_export(self):
        self._assert_reexport_audited(
            f"/download_request_json/{self.exported_req.id}/"
        )

    def test_all_guests_reexport_confirmed_emits_re_export(self):
        self._assert_reexport_audited(
            f"/download_all_guests_json/{self.event.id}/"
        )


class EventDeleteAuditTests(AuditChecklistMixin, TestCase):
    """AC-4: event.delete на всех трёх живых путях; obj_id захвачен ДО .delete()."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="su2", password=PASSWORD, email=""
        )

    def test_legacy_delete_event_is_audited(self):
        event = Event.objects.create(name_rus="Удаляемое", title="Del")
        event_id = event.id
        self.client.force_login(self.superuser)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(f"/delete_event/{event_id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Event.objects.filter(id=event_id).exists())
        records = self._records_for(cm, "event.delete")
        self.assertEqual(len(records), 1)
        # obj_id захвачен ДО .delete() — иначе тут было бы "None" (pk обнулён).
        self.assertEqual(records[0].obj_id, str(event_id))

    def test_flush_outdated_events_audits_each_deleted_event(self):
        today = date.today()
        e1 = Event.objects.create(
            name_rus="Старое-1", date_end=today - timedelta(days=10)
        )
        e2 = Event.objects.create(
            name_rus="Старое-2", date_end=today - timedelta(days=20)
        )
        expected_ids = {str(e1.id), str(e2.id)}
        self.client.force_login(self.superuser)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.get("/flush_outdated_events/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Event.objects.filter(id__in=[e1.id, e2.id]).exists())
        records = self._records_for(cm, "event.delete")
        # Аудит на КАЖДЫЙ удаляемый Event, не одной строкой на batch (AC-4);
        # user=request.user (интерактивный view), не system/None.
        self.assertEqual({r.obj_id for r in records}, expected_ids)
        self.assertEqual(len(records), 2)
        self.assertEqual(
            {r.user_id for r in records}, {self.superuser.id}
        )

    def test_drf_event_destroy_is_audited(self):
        event = Event.objects.create(name_rus="ДРФ", title="API")
        event_id = event.id
        su_user, _ = _make_operator("supero3", "superoperator")
        client = APIClient()
        client.force_authenticate(su_user)
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = client.delete(f"/api/v1/events/{event_id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Event.objects.filter(id=event_id).exists())
        records = self._records_for(cm, "event.delete")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].obj_id, str(event_id))


class RequestDeleteAuditTests(AuditChecklistMixin, TestCase):
    """AC-4: request.delete на всех трёх живых локалях (RU/KZ/EN)."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="su3", password=PASSWORD, email=""
        )
        self.event = Event.objects.create(name_rus="E", title="E")
        op_user, self.operator = _make_operator("oper4", "operator", event=self.event)
        self.client.force_login(self.superuser)

    def _assert_delete_audited(self, url_prefix):
        req = _make_request(self.event, self.operator)
        req_id = req.id
        with self.assertLogs("eventproject", level="INFO") as cm:
            resp = self.client.post(f"{url_prefix}/delete_request/{req_id}/")
        self.assertEqual(resp.status_code, 302)  # успех → redirect на /application/
        self.assertFalse(Request.objects.filter(id=req_id).exists())
        records = self._records_for(cm, "request.delete")
        self.assertEqual(len(records), 1)
        # obj_id захвачен ДО .delete() (иначе "None" — pk обнулён Django).
        self.assertEqual(records[0].obj_id, str(req_id))

    def test_ru_delete_request_is_audited(self):
        self._assert_delete_audited("")

    def test_kz_delete_request_is_audited(self):
        self._assert_delete_audited("/kz")

    def test_en_delete_request_is_audited(self):
        self._assert_delete_audited("/en")
