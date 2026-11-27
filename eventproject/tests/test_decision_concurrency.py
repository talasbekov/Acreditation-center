"""Story fe-3.6 — durable audit решений: атомарность, конкуренция, append-only.

Покрытие AC:
  • AC-1 — атомарность + fault-injection: мок `AuditLog.objects.create` бросает → статус
    заявки НЕ меняется (реальный откат, не «зелёный театр» на stdout) — для approve И return.
  • AC-2 — конкуренция (Murat, HIGH): `select_for_update` row-lock → при параллельных
    решениях по одному id один коммитит, второй ловит 409; РОВНО одна audit-строка;
    `return_count` без lost-update. Параллельные транзакции (`TransactionTestCase`+потоки),
    `@skipUnless(postgres)` — SQLite не энфорсит FOR UPDATE row-lock.
  • AC-3 — append-only на уровне БД: bulk `.update()/.delete()` и instance `save(pk)/delete()`
    → IntegrityError (портируемо); Postgres-триггер BEFORE UPDATE/DELETE (raw SQL мимо ORM) —
    `@skipUnless(postgres)`.

Реализация 3.6 = concurrency-guard (реш.#2): durable-аудит + append-only УЖЕ доставлены hd-4.1
(`audit.py::audit_log` → `AuditLog`, три слоя guard). Эти тесты ДОКАЗЫВАЮТ гарантии на решениях.
"""

import threading
from unittest import skipUnless
from unittest.mock import patch

from django.db import IntegrityError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from eventproject.models import AuditLog, Event
from eventproject.tests.test_attendee_api import (
    VALID_IIN,
    _make_attendee,
    _make_operator,
    _make_request,
)

REASON = "Фото не соответствует требованиям 3×4"


# ═══════════════════════════════════════════════════════════════════════════
# AC-1 — Атомарность / fault-injection (rollback при сбое durable-аудита)
# ═══════════════════════════════════════════════════════════════════════════
class DecisionAuditAtomicityTests(TestCase):
    def setUp(self):
        self.event1 = Event.objects.create(name_rus="Событие 1", title="E1")
        self.su_user, self.su = _make_operator("su", "superoperator")
        self.op_user, self.op = _make_operator("op", "operator", event=self.event1)
        self.req1 = _make_request(self.event1, self.op)
        self.att = _make_attendee(
            self.req1, surname="Беков", status="in_review", iin=VALID_IIN
        )
        self.client = APIClient()
        self.client.force_authenticate(self.su_user)

    def test_approve_rolls_back_status_when_audit_write_fails(self):
        # AC-1: сбой durable-записи (`AuditLog.objects.create`) внутри transaction.atomic
        # ОТКАТЫВАЕТ смену статуса — не «одобрено на stdout, но не в БД».
        with patch.object(
            AuditLog.objects, "create", side_effect=RuntimeError("audit sink boom")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(f"/api/v1/attendees/{self.att.id}/approve/", {}, format="json")
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, "in_review")  # откат: статус НЕ изменился
        self.assertEqual(
            AuditLog.objects.filter(action="attendee.approved", obj_id=str(self.att.id)).count(),
            0,
        )

    def test_return_rolls_back_status_and_count_when_audit_write_fails(self):
        with patch.object(
            AuditLog.objects, "create", side_effect=RuntimeError("audit sink boom")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    f"/api/v1/attendees/{self.att.id}/return/", {"reason": REASON}, format="json"
                )
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, "in_review")  # откат
        self.assertEqual(self.att.return_count, 0)       # счётчик не инкрементнулся
        self.assertIsNone(self.att.last_return_reason)
        self.assertEqual(  # review P5 — симметрия с approve: durable-строки возврата тоже нет
            AuditLog.objects.filter(action="attendee.returned", obj_id=str(self.att.id)).count(), 0
        )

    def test_successful_decision_writes_exactly_one_durable_row(self):
        # Позитив: без сбоя — ровно одна durable audit-строка с before/after-статусом.
        resp = self.client.post(f"/api/v1/attendees/{self.att.id}/approve/", {}, format="json")
        self.assertEqual(resp.status_code, 200)  # review P5 — success-path явно 200 (не только по audit)
        rows = AuditLog.objects.filter(action="attendee.approved", obj_id=str(self.att.id))
        self.assertEqual(rows.count(), 1)
        extra = rows.first().extra
        self.assertEqual(extra["from"], "in_review")
        self.assertEqual(extra["to"], "ready")


# ═══════════════════════════════════════════════════════════════════════════
# AC-3 — Append-only на уровне БД (негативные тесты)
# ═══════════════════════════════════════════════════════════════════════════
class AuditLogAppendOnlyTests(TestCase):
    def setUp(self):
        self.log = AuditLog.objects.create(
            actor_id=1, role="superoperator", action="attendee.approved",
            obj_type="Attendee", obj_id="1", ip="127.0.0.1", extra={"from": "in_review", "to": "ready"},
        )

    def test_bulk_update_forbidden(self):
        with self.assertRaises(IntegrityError):
            AuditLog.objects.filter(pk=self.log.pk).update(action="tampered")

    def test_bulk_delete_forbidden(self):
        with self.assertRaises(IntegrityError):
            AuditLog.objects.filter(pk=self.log.pk).delete()

    def test_instance_update_forbidden(self):
        self.log.action = "tampered"
        with self.assertRaises(IntegrityError):
            self.log.save()

    def test_instance_delete_forbidden(self):
        with self.assertRaises(IntegrityError):
            self.log.delete()

    @skipUnless(connection.vendor == "postgresql", "DB-триггер append-only — только Postgres (миграция 0025)")
    def test_db_trigger_blocks_raw_sql_update_delete(self):
        # AC-3: append-only на УРОВНЕ БД (не только ORM-guard) — сырой SQL мимо ORM тоже блокируется.
        table = AuditLog._meta.db_table
        # review P3 — каждый raw-SQL в СВОЁМ savepoint: иначе первый UPDATE рвёт транзакцию
        # (trigger RAISE) → DELETE падает InFailedSqlTransaction НЕЗАВИСИМО от delete-триггера
        # (ложно-зелёный). Отдельные atomic → DELETE-триггер проверяется на чистой транзакции.
        with self.assertRaises(Exception):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(f"UPDATE {table} SET action='tampered' WHERE id=%s", [self.log.pk])
        with self.assertRaises(Exception):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(f"DELETE FROM {table} WHERE id=%s", [self.log.pk])


# ═══════════════════════════════════════════════════════════════════════════
# AC-2 — Конкуренция (параллельные транзакции; select_for_update row-lock)
# SQLite не энфорсит FOR UPDATE → реальный race только на Postgres.
# ═══════════════════════════════════════════════════════════════════════════
@skipUnless(
    connection.vendor == "postgresql",
    "select_for_update row-lock энфорсится только на Postgres; SQLite race не воспроизводит",
)
class DecisionConcurrencyRaceTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.event1 = Event.objects.create(name_rus="Событие 1", title="E1")
        self.su_user, self.su = _make_operator("su", "superoperator")
        self.op_user, self.op = _make_operator("op", "operator", event=self.event1)
        self.req1 = _make_request(self.event1, self.op)
        self.att = _make_attendee(
            self.req1, surname="Беков", status="in_review", iin=VALID_IIN
        )

    def _post(self, path, body, barrier, results, errors, idx):
        barrier.wait()  # обе транзакции стартуют одновременно → реальная гонка на row-lock
        client = APIClient()
        client.force_authenticate(self.su_user)
        try:
            resp = client.post(path, body, format="json")
            results[idx] = resp.status_code
        except Exception as exc:  # review P4 — сбой воркера (напр. регресс в 500) НЕ должен молча
            errors[idx] = exc     # исчезать в потоке и маскироваться как length-mismatch → ловим.
        finally:
            connections.close_all()  # закрыть per-thread соединение

    def _run_parallel(self, paths_bodies):
        barrier = threading.Barrier(len(paths_bodies))
        results = {}
        errors = {}
        threads = [
            threading.Thread(target=self._post, args=(p, b, barrier, results, errors, i))
            for i, (p, b) in enumerate(paths_bodies)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if errors:  # review P4 — воркер бросил исключение (не вернул 200/409) → падаем громко
            raise AssertionError(f"worker thread(s) raised: {errors}")
        return sorted(results.values())

    def test_parallel_approve_exactly_one_wins(self):
        path = f"/api/v1/attendees/{self.att.id}/approve/"
        codes = self._run_parallel([(path, {}), (path, {})])
        self.assertEqual(codes, [200, 409])  # один коммит, второй — конфликт
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, "ready")
        self.assertEqual(
            AuditLog.objects.filter(action="attendee.approved", obj_id=str(self.att.id)).count(),
            1,  # РОВНО одна audit-строка, не две
        )

    def test_parallel_return_no_lost_update_and_single_audit(self):
        path = f"/api/v1/attendees/{self.att.id}/return/"
        codes = self._run_parallel([(path, {"reason": REASON}), (path, {"reason": REASON})])
        self.assertEqual(codes, [200, 409])
        self.att.refresh_from_db()
        self.assertEqual(self.att.status, "submitted")
        self.assertEqual(self.att.return_count, 1)  # не lost-update (не 2 успеха)
        self.assertEqual(
            AuditLog.objects.filter(action="attendee.returned", obj_id=str(self.att.id)).count(),
            1,
        )

    def test_parallel_approve_vs_return_one_decision_wins(self):
        codes = self._run_parallel([
            (f"/api/v1/attendees/{self.att.id}/approve/", {}),
            (f"/api/v1/attendees/{self.att.id}/return/", {"reason": REASON}),
        ])
        self.assertEqual(codes, [200, 409])  # ровно одно решение проходит
        self.att.refresh_from_db()
        self.assertIn(self.att.status, ("ready", "submitted"))
        total = (
            AuditLog.objects.filter(obj_id=str(self.att.id))
            .filter(action__in=["attendee.approved", "attendee.returned"])
            .count()
        )
        self.assertEqual(total, 1)  # одно решение → одна запись, не две конфликтующих
