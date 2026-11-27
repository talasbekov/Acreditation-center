"""Story hd-4.1: AuditLog — append-only DB-модель + sync transactional write-path."""
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection, transaction
from django.test import TestCase

from eventproject.audit import audit_log
from eventproject.models import AuditLog


class AuditLogModelTests(TestCase):
    """AC-1 (поля/запись) · AC-3 (model-level append-only guard)."""

    def test_audit_log_writes_db_row_with_fields(self):
        """AC-1: audit_log() пишет ровно одну строку AuditLog с корректными полями."""
        user = User.objects.create_user(username="op1", password="x")
        audit_log(
            user,
            action="attendee.returned",
            obj_type="Attendee",
            obj_id=42,
            ip="10.0.0.1",
            extra={"reason": "blurry photo"},
        )
        rows = AuditLog.objects.all()
        self.assertEqual(rows.count(), 1)
        row = rows.first()
        self.assertEqual(row.actor_id, user.id)
        self.assertEqual(row.action, "attendee.returned")
        self.assertEqual(row.obj_type, "Attendee")
        self.assertEqual(row.obj_id, "42")  # str-нормализация
        self.assertEqual(row.ip, "10.0.0.1")
        self.assertEqual(row.extra, {"reason": "blurry photo"})
        self.assertIsNotNone(row.created_at)

    def test_audit_log_system_actor_null(self):
        """AC-1: user=None → actor_id null, role=system (Celery/unauthenticated)."""
        audit_log(None, action="import.run", obj_type="ImportLog", obj_id=1, ip="celery")
        row = AuditLog.objects.get()
        self.assertIsNone(row.actor_id)
        self.assertEqual(row.role, "system")

    def test_audit_log_keeps_stdout_mirror(self):
        """AC-1: stdout-зеркало сохраняется (logger.info 'audit')."""
        with self.assertLogs("eventproject", level="INFO") as cm:
            audit_log(None, action="x.y", obj_type="T", obj_id=1, ip="i")
        self.assertTrue(any("audit" in r.getMessage() for r in cm.records))

    def test_model_guard_blocks_update(self):
        """AC-3: повторный save() существующей строки → запрещён (портируемо, SQLite)."""
        row = AuditLog.objects.create(action="a", obj_type="T", obj_id="1", ip="i")
        row.action = "tampered"
        with self.assertRaises(Exception):
            row.save()

    def test_model_guard_blocks_delete(self):
        """AC-3: delete() строки → запрещён."""
        row = AuditLog.objects.create(action="a", obj_type="T", obj_id="1", ip="i")
        with self.assertRaises(Exception):
            row.delete()

    def test_manager_guard_blocks_queryset_update(self):
        """AC-3 (review-patch): bulk QuerySet.update() запрещён ПОРТИРУЕМО (SQLite)."""
        row = AuditLog.objects.create(action="a", obj_type="T", obj_id="1", ip="i")
        with self.assertRaises(Exception):
            AuditLog.objects.filter(pk=row.pk).update(action="tampered")
        row.refresh_from_db()
        self.assertEqual(row.action, "a")  # не изменилось

    def test_manager_guard_blocks_queryset_delete(self):
        """AC-3 (review-patch): bulk QuerySet.delete() запрещён ПОРТИРУЕМО (SQLite)."""
        row = AuditLog.objects.create(action="a", obj_type="T", obj_id="1", ip="i")
        with self.assertRaises(Exception):
            AuditLog.objects.filter(pk=row.pk).delete()
        self.assertTrue(AuditLog.objects.filter(pk=row.pk).exists())  # не удалилось


class AuditLogTransactionTests(TestCase):
    """AC-2: сбой записи audit откатывает вызывающую мутацию."""

    def test_audit_failure_rolls_back_caller_mutation(self):
        with patch(
            "eventproject.audit.AuditLog.objects.create",
            side_effect=RuntimeError("audit sink down"),
        ):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    User.objects.create_user(username="should_rollback", password="x")
                    audit_log(None, action="x", obj_type="T", obj_id=1, ip="i")
        # мутация откатилась — пользователь не создан
        self.assertFalse(User.objects.filter(username="should_rollback").exists())


class AuditLogPiiTests(TestCase):
    """AC-4: сырой ИИН (12 цифр) не сохраняется в extra."""

    def test_raw_iin_not_stored_in_extra(self):
        audit_log(
            None,
            action="attendee.iin_discarded",
            obj_type="Attendee",
            obj_id=1,
            ip="i",
            extra={"iin": "990101350511"},  # сырой 12-значный — должен быть вычищен
        )
        row = AuditLog.objects.get()
        import json

        serialized = json.dumps(row.extra, ensure_ascii=False)
        import re

        self.assertIsNone(
            re.search(r"\b\d{12}\b", serialized),
            f"raw IIN leaked into audit extra: {serialized}",
        )

    def test_raw_iin_as_int_not_stored_in_extra(self):
        """AC-4 (review-patch): ИИН-int (не str) тоже маскируется — не утекает."""
        import json
        import re

        audit_log(
            None,
            action="attendee.iin_discarded",
            obj_type="Attendee",
            obj_id=1,
            ip="i",
            extra={"iin": 990101350511},  # сырой ИИН как int
        )
        row = AuditLog.objects.get()
        serialized = json.dumps(row.extra, ensure_ascii=False)
        self.assertIsNone(
            re.search(r"\b\d{12}\b", serialized),
            f"raw int IIN leaked into audit extra: {serialized}",
        )


class AuditLogConcurrencyTests(TestCase):
    """AC-5: N последовательных вызовов → N строк (без потерь/дублей)."""

    def test_n_calls_n_rows(self):
        for i in range(5):
            audit_log(None, action="a", obj_type="T", obj_id=i, ip="i")
        self.assertEqual(AuditLog.objects.count(), 5)


class AuditLogPostgresTriggerTests(TestCase):
    """AC-3 (DB-уровень): Postgres-триггер блокирует bulk UPDATE/DELETE в обход ORM.

    На SQLite (settings_test CI) пропускается — там защита на model-guard
    (AuditLogModelTests). Прецедент кросс-БД skip — P2-4 (cyrillic ILIKE).
    """

    @skipUnless(
        connection.vendor == "postgresql", "append-only DB-триггер только на Postgres"
    )
    def test_trigger_blocks_queryset_update_and_delete(self):
        row = AuditLog.objects.create(action="a", obj_type="T", obj_id="1", ip="i")
        with self.assertRaises(Exception):
            AuditLog.objects.filter(pk=row.pk).update(action="tampered")
        with self.assertRaises(Exception):
            AuditLog.objects.filter(pk=row.pk).delete()
