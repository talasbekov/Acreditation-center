"""Миграция 0036: дубль причины возврата last_return_reason удаляется без потери текста."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from eventproject.models import Attendee, Event
from eventproject.tests.test_attendee_api import (
    VALID_IIN,
    _make_attendee,
    _make_operator,
    _make_request,
)

BEFORE = ("eventproject", "0035_attendee_dateadd_idx")
AFTER = ("eventproject", "0036_remove_attendee_last_return_reason")


def _migrate_to_latest():
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())


class ReturnReasonMigrationTests(TransactionTestCase):
    def setUp(self):
        event = Event.objects.create(name_rus="Событие", title="E")
        _, operator = _make_operator("op-mig", "operator", event=event)
        self.request = _make_request(event, operator)
        MigrationExecutor(connection).migrate([BEFORE])
        self.addCleanup(_migrate_to_latest)
        self.old = MigrationExecutor(connection).loader.project_state([BEFORE]).apps.get_model(
            "eventproject", "Attendee"
        ).objects

    def _attendee(self, surname, status, review_comment, last_reason, count):
        att = _make_attendee(self.request, surname=surname, status=status, iin=VALID_IIN)
        self.old.filter(pk=att.pk).update(
            review_comment=review_comment, last_return_reason=last_reason, return_count=count
        )
        return att.pk

    def test_forward_keeps_reason_text(self):
        # Возврат до сведения линий: причина только в last_return_reason.
        branch_era = self._attendee("Ветка", "submitted", "", "Нет фото", 1)
        # Возврат после сведения: причина в обоих полях — review_comment не трогаем.
        both = self._attendee("Оба", "draft", "Скан нечитаем", "Скан нечитаем", 2)
        # Повторно отправлен: review_comment очищен, last_return_reason помнит причину.
        resubmitted = self._attendee("Снова", "submitted", "", "Старая причина", 1)
        plain = self._attendee("Обычный", "draft", "", None, 0)

        MigrationExecutor(connection).migrate([AFTER])

        got = dict(Attendee.objects.values_list("pk", "review_comment"))
        self.assertEqual(got[branch_era], "Нет фото")
        self.assertEqual(got[both], "Скан нечитаем")
        self.assertEqual(got[resubmitted], "Старая причина")
        self.assertEqual(got[plain], "")
        # «Возвращён» считается только для черновика: повторно отправленный не стал возвращённым.
        self.assertEqual(Attendee.objects.get(pk=resubmitted).status, "submitted")

    def test_backward_restores_last_return_reason(self):
        returned = self._attendee("Возврат", "draft", "Нет подписи", "Нет подписи", 1)
        MigrationExecutor(connection).migrate([AFTER])
        executor = MigrationExecutor(connection)
        executor.migrate([BEFORE])
        old = executor.loader.project_state([BEFORE]).apps.get_model("eventproject", "Attendee").objects
        self.assertEqual(old.get(pk=returned).last_return_reason, "Нет подписи")
