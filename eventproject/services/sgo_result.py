"""Исполнение результата проверки СГО по пакету выгрузки (второй этап).

Файл результата (JSON) от СГО:

    {"export_id": "<package_id>", "event_id": 12, "denied_participant_ids": [101, 205]}

Участники пакета из списка → доступ запрещён (`access_status = "no"`), остальные
участники пакета → разрешён (`"yes"`). Пустой список — разрешено всем. Исполнять
пакет можно повторно: решения перезаписываются по последнему файлу.
"""

import json

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from eventproject.audit import audit_log
from eventproject.errors import CodedValidationError
from eventproject.models import Attendee, ExportLog


class ResultError(CodedValidationError):
    pass


def parse_result(raw):
    """Файл или тело запроса → dict. Ошибка формата — `sgo_result_invalid`."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ResultError("sgo_result_invalid", field="result")
    if not isinstance(raw, dict):
        raise ResultError("sgo_result_invalid", field="result")
    return raw


def execute(export_log_id, payload, user, ip=""):
    """Применить результат проверки. Возвращает сводку {allowed, denied, total}."""
    with transaction.atomic():
        export_log = ExportLog.objects.select_for_update().get(pk=export_log_id)
        ids = export_log.attendee_ids
        if not ids:
            raise ResultError("sgo_result_no_package", field="result")

        export_id = payload.get("export_id")
        if export_id not in (None, "") and str(export_id) != str(export_log.package_id):
            raise ResultError("sgo_result_wrong_package", field="result")
        event_id = payload.get("event_id")
        if event_id not in (None, "") and str(event_id) != str(export_log.event_id):
            raise ResultError("sgo_result_wrong_package", field="result")

        denied_raw = payload.get("denied_participant_ids", [])
        if not isinstance(denied_raw, list):
            raise ResultError("sgo_result_invalid", field="result")
        try:
            denied = {int(x) for x in denied_raw}
        except (TypeError, ValueError):
            raise ResultError("sgo_result_invalid", field="result")
        unknown = sorted(denied - set(ids))
        if unknown:
            raise CodedValidationError(
                "sgo_result_unknown_ids", field="result", params={"ids": ", ".join(map(str, unknown[:20]))}
            )

        now = timezone.now()
        present = Attendee.objects.filter(pk__in=ids)
        denied_count = present.filter(pk__in=denied).update(access_status="no", access_decided_at=now)
        allowed_count = present.exclude(pk__in=denied).update(access_status="yes", access_decided_at=now)

        export_log.executed_at = now
        export_log.executed_by = user
        export_log.denied_ids = sorted(denied)
        export_log.save(update_fields=["executed_at", "executed_by", "denied_ids"])
        audit_log(
            user=user, action="export.executed", obj_type="ExportLog", obj_id=str(export_log.pk), ip=ip or "",
            extra={"package_id": str(export_log.package_id), "allowed": allowed_count, "denied": denied_count},
        )
        event_id = export_log.event_id
        transaction.on_commit(lambda: cache.delete(f"dashboard:event:{event_id}"))
    return {"allowed": allowed_count, "denied": denied_count, "total": allowed_count + denied_count}
