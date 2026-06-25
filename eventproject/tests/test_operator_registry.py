"""Story 2.4 — тесты реестра операторов и истории доступа (AC-6)."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from eventproject.models import Category, Event, Operator, OperatorAccessEvent


def _make_operator(
    username,
    role="operator",
    *,
    first_name="Иван",
    last_name="Иванов",
    patronymic="Иванович",
    is_active=True,
    is_superuser=False,
    password="StrongPass123!",
    email=None,
    email_status="pending",
):
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email if email is not None else f"{username}@example.com",
        first_name=first_name,
        last_name=last_name,
        is_active=is_active,
        is_superuser=is_superuser,
    )
    operator = Operator.objects.create(
        user=user, role=role, patronymic=patronymic, email_status=email_status
    )
    return user, operator


def _set_last_login(user, value):
    User.objects.filter(pk=user.pk).update(last_login=value)
    user.refresh_from_db()


class OperatorRegistryListTests(TestCase):
    def setUp(self):
        self.superop_user, _ = _make_operator("superop", "superoperator")
        self.client = APIClient()
        self.client.force_authenticate(user=self.superop_user)

    def test_list_returns_all_fields(self):
        _make_operator(
            "petrov", last_name="Петров", email_status="sent"
        )
        resp = self.client.get("/api/v1/operators/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data)
        row = next(r for r in resp.data["results"] if r["username"] == "petrov")
        for field in (
            "id", "user_id", "username", "email", "first_name", "last_name",
            "patronymic", "full_name", "role", "events", "category",
            "email_status", "email_status_display", "date_joined",
            "last_login", "is_active", "inactivity_warning",
        ):
            self.assertIn(field, row)
        self.assertEqual(row["email_status_display"], "Отправлено")
        self.assertIn("Петров", row["full_name"])

    def test_email_status_display_mapping(self):
        _make_operator("pend", email_status="pending")
        _make_operator("err", email_status="error")
        resp = self.client.get("/api/v1/operators/")
        by_user = {r["username"]: r for r in resp.data["results"]}
        self.assertEqual(by_user["pend"]["email_status_display"], "Не отправлено")
        self.assertEqual(by_user["err"]["email_status_display"], "Ошибка")

    def test_non_superoperator_forbidden(self):
        op_user, _ = _make_operator("plain", "operator")
        client = APIClient()
        client.force_authenticate(user=op_user)
        resp = client.get("/api/v1/operators/")
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_forbidden(self):
        resp = APIClient().get("/api/v1/operators/")
        self.assertIn(resp.status_code, (401, 403))

    def test_search_by_name(self):
        _make_operator("sidorov", last_name="Сидоров")
        _make_operator("kuznetsov", last_name="Кузнецов")
        resp = self.client.get("/api/v1/operators/", {"search": "Сидоров"})
        self.assertEqual(resp.status_code, 200)
        usernames = [r["username"] for r in resp.data["results"]]
        self.assertIn("sidorov", usernames)
        self.assertNotIn("kuznetsov", usernames)

    def test_filter_by_event(self):
        event = Event.objects.create(name_rus="Событие A", title="Событие A")
        _, op_with = _make_operator("withev")
        op_with.events.add(event)
        _make_operator("noev")
        resp = self.client.get("/api/v1/operators/", {"event_id": event.id})
        self.assertEqual(resp.status_code, 200)
        usernames = [r["username"] for r in resp.data["results"]]
        self.assertIn("withev", usernames)
        self.assertNotIn("noev", usernames)

    def test_filter_by_email_status(self):
        _make_operator("s1", email_status="sent")
        _make_operator("e1", email_status="error")
        resp = self.client.get("/api/v1/operators/", {"email_status": "sent"})
        statuses = {r["email_status"] for r in resp.data["results"]}
        self.assertEqual(statuses, {"sent"})

    def test_invalid_event_id_returns_400(self):
        resp = self.client.get("/api/v1/operators/", {"event_id": "abc"})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_email_status_returns_400(self):
        resp = self.client.get("/api/v1/operators/", {"email_status": "bogus"})
        self.assertEqual(resp.status_code, 400)

    def test_inactivity_warning_boundary(self):
        # никогда не входил → warning
        _make_operator("never")
        # вошёл давно (>30д) → warning
        _, op_old = _make_operator("old")
        _set_last_login(op_old.user, timezone.now() - timedelta(days=40))
        # вошёл недавно → нет warning
        _, op_fresh = _make_operator("fresh")
        _set_last_login(op_fresh.user, timezone.now())

        resp = self.client.get("/api/v1/operators/")
        by_user = {r["username"]: r for r in resp.data["results"]}
        self.assertTrue(by_user["never"]["inactivity_warning"])
        self.assertTrue(by_user["old"]["inactivity_warning"])
        self.assertFalse(by_user["fresh"]["inactivity_warning"])


class OperatorRegistryDetailTests(TestCase):
    def setUp(self):
        self.superop_user, _ = _make_operator("superop", "superoperator")
        self.client = APIClient()
        self.client.force_authenticate(user=self.superop_user)

    def test_detail_contains_access_history(self):
        _, op = _make_operator("hist")
        now = timezone.now()
        OperatorAccessEvent.objects.create(
            operator=op, event_type="login", actor=op.user,
            timestamp=now - timedelta(days=5),
        )
        OperatorAccessEvent.objects.create(
            operator=op, event_type="login", actor=op.user, timestamp=now,
        )
        OperatorAccessEvent.objects.create(
            operator=op, event_type="password_changed", actor=op.user, timestamp=now,
        )
        resp = self.client.get(f"/api/v1/operators/{op.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        self.assertIn("created_at", data)
        self.assertIsNotNone(data["first_login_at"])
        self.assertEqual(len(data["password_changes"]), 1)
        # 3 события в хронологии
        self.assertEqual(len(data["access_events"]), 3)

    def test_detail_serialization_uses_prefetch_no_extra_queries(self):
        # BE-2: get_first_login_at / get_password_changes не должны бить .filter()
        # мимо prefetch access_events → сериализация уже-префетченного оператора
        # = 0 дополнительных запросов (раньше 2: login-filter + password-filter).
        from eventproject.serializers.operator import (
            OperatorRegistryDetailSerializer,
        )

        _, op = _make_operator("nplus1")
        now = timezone.now()
        for i in range(3):
            OperatorAccessEvent.objects.create(
                operator=op, event_type="login", actor=op.user,
                timestamp=now - timedelta(days=i),
            )
        OperatorAccessEvent.objects.create(
            operator=op, event_type="password_changed", actor=op.user, timestamp=now,
        )

        # Префетч как в OperatorViewSet.get_queryset() для action="retrieve".
        obj = (
            Operator.objects.select_related("user", "category")
            .prefetch_related("events", "access_events__actor")
            .get(pk=op.pk)
        )
        with self.assertNumQueries(0):
            data = OperatorRegistryDetailSerializer(obj).data
            _ = (
                data["first_login_at"],
                data["password_changes"],
                data["access_events"],
                data["access_events_total"],
                data["access_events_has_more"],
            )

    def test_access_events_truncation_exposes_total_and_has_more(self):
        # BE-3: при >50 событий список молча режется до 50; total/has_more
        # раскрывают усечение клиенту (раньше — тихая потеря истории).
        _, op = _make_operator("manyev")
        now = timezone.now()
        OperatorAccessEvent.objects.bulk_create(
            [
                OperatorAccessEvent(
                    operator=op, event_type="login", actor=op.user,
                    timestamp=now - timedelta(minutes=i),
                )
                for i in range(55)
            ]
        )

        resp = self.client.get(f"/api/v1/operators/{op.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        self.assertEqual(len(data["access_events"]), 50)
        self.assertEqual(data["access_events_total"], 55)
        self.assertTrue(data["access_events_has_more"])


class OperatorDeactivationTests(TestCase):
    def setUp(self):
        self.superop_user, _ = _make_operator("superop", "superoperator")
        self.client = APIClient()
        self.client.force_authenticate(user=self.superop_user)

    @patch("eventproject.views.operator_api.audit_log")
    def test_deactivate_sets_inactive_and_logs(self, mock_audit):
        target_user, op = _make_operator("target")
        resp = self.client.post(f"/api/v1/operators/{op.id}/deactivate/")
        self.assertEqual(resp.status_code, 200)
        target_user.refresh_from_db()
        self.assertFalse(target_user.is_active)
        self.assertTrue(
            OperatorAccessEvent.objects.filter(
                operator=op, event_type="deactivated"
            ).exists()
        )
        mock_audit.assert_called_once()
        self.assertEqual(
            mock_audit.call_args.kwargs["action"], "operator.deactivate"
        )

    def test_reactivate_restores_access(self):
        target_user, op = _make_operator("target2", is_active=False)
        resp = self.client.post(f"/api/v1/operators/{op.id}/reactivate/")
        self.assertEqual(resp.status_code, 200)
        target_user.refresh_from_db()
        self.assertTrue(target_user.is_active)
        self.assertTrue(
            OperatorAccessEvent.objects.filter(
                operator=op, event_type="reactivated"
            ).exists()
        )

    def test_cannot_deactivate_self(self):
        op = Operator.objects.get(user=self.superop_user)
        resp = self.client.post(f"/api/v1/operators/{op.id}/deactivate/")
        self.assertEqual(resp.status_code, 400)
        self.superop_user.refresh_from_db()
        self.assertTrue(self.superop_user.is_active)

    def test_cannot_deactivate_superuser(self):
        su_user, su_op = _make_operator("root", "superuser", is_superuser=True)
        resp = self.client.post(f"/api/v1/operators/{su_op.id}/deactivate/")
        self.assertEqual(resp.status_code, 400)
        su_user.refresh_from_db()
        self.assertTrue(su_user.is_active)

    def test_cannot_deactivate_peer_superoperator(self):
        # P2-1: супероператор НЕ может деактивировать другого супероператора —
        # иначе два супероператора могут заблокировать друг друга.
        peer_user, peer_op = _make_operator("peer_superop", "superoperator")
        resp = self.client.post(f"/api/v1/operators/{peer_op.id}/deactivate/")
        self.assertEqual(resp.status_code, 403)
        peer_user.refresh_from_db()
        self.assertTrue(peer_user.is_active)

    def test_superuser_can_deactivate_superoperator(self):
        # P2-1: суперпользователь (админ) — может (guard только для супероператора-актора).
        su_user, _ = _make_operator("root_admin", "superuser", is_superuser=True)
        client = APIClient()
        client.force_authenticate(user=su_user)
        peer_user, peer_op = _make_operator("victim_superop", "superoperator")
        resp = client.post(f"/api/v1/operators/{peer_op.id}/deactivate/")
        self.assertEqual(resp.status_code, 200)
        peer_user.refresh_from_db()
        self.assertFalse(peer_user.is_active)


class OperatorLoginAccessTests(TestCase):
    """Логин-флоу: запись события входа + сообщение о деактивации (AC-3/AC-4)."""

    def test_active_operator_login_records_event(self):
        user, op = _make_operator("loginop", password="StrongPass123!")
        client = Client()
        resp = client.post(
            "/user_login/",
            {"username": "loginop", "password": "StrongPass123!"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            OperatorAccessEvent.objects.filter(
                operator=op, event_type="login"
            ).exists()
        )

    def test_deactivated_operator_sees_localized_message(self):
        _make_operator(
            "deadop", is_active=False, password="StrongPass123!"
        )
        client = Client()
        resp = client.post(
            "/user_login/",
            {"username": "deadop", "password": "StrongPass123!"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Аккаунт деактивирован", resp.content.decode("utf-8"))

    @override_settings(AXES_FAILURE_LIMIT=2)
    def test_locked_out_sees_localized_message_not_english(self):
        # BE-1: при axes-lockout оператор должен видеть локализованное сообщение
        # о блокировке (а не голый англоязычный axes-429 «Account locked»).
        _make_operator("lockme", password="StrongPass123!")
        client = Client()
        # Превышаем лимит неверными паролями → источник блокируется по ip.
        for _ in range(2):
            client.post(
                "/user_login/", {"username": "lockme", "password": "WRONG"}
            )
        # Даже верный пароль теперь не проходит — но сообщение должно быть
        # русским/понятным, не английским axes-дефолтом.
        resp = client.post(
            "/user_login/", {"username": "lockme", "password": "StrongPass123!"},
        )
        body = resp.content.decode("utf-8", "replace")
        self.assertIn("заблокир", body.lower())
        self.assertNotIn("Account locked", body)
