"""Story 4.3 — вью delta-экспорта (Супероператор).

POST `export_delta/<event_id>/<request_id>/`: формирует ZIP (attendees.json + медиа)
из новых `ready`-участников категории, создаёт ExportLog, переводит выгруженных
`ready → exported`, пишет audit_log — атомарно. Архив отдаётся только после commit.
"""

import re
import tempfile
from datetime import timezone as dt_timezone
from pathlib import Path

from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from eventproject.audit import audit_log
from eventproject.models import Attendee, Event, ExportLog, Request
from eventproject.services import export as export_service
from eventproject.state_machine import AttendeeStatus
from eventproject.views.dashboard import _is_superoperator


def _safe_category(name):
    """Безопасное имя категории для имени файла архива."""
    cleaned = re.sub(r"[^\w.-]+", "_", name or "", flags=re.UNICODE).strip("_")
    return cleaned or "all"


def _no_new_response(last_export):
    """Сообщение AC-5: новых записей нет (ZIP/ExportLog/смены статусов не происходит)."""
    if last_export:
        when = timezone.localtime(last_export.exported_before).strftime("%d.%m.%Y %H:%M")
        msg = f"Нет новых записей с момента последнего экспорта ({when})"
    else:
        msg = "Нет записей со статусом «ready» для экспорта в этой категории"
    return HttpResponse(msg, content_type="text/plain; charset=utf-8")


@require_POST
@csrf_protect
def export_delta(request, event_id, request_id):
    # Аноним → на логин (302); аутентифицированный без прав → 403 (как дашборд 4.2).
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url="/user_login/")
    if not _is_superoperator(request.user):
        raise PermissionDenied

    event = get_object_or_404(Event, pk=event_id)
    category = get_object_or_404(Request, pk=request_id, event=event)

    # D4 (ревью 4.3): event_code обязателен по контракту v1.0 (required, nullable=false).
    # Без него attendees.json был бы невалиден — fail-fast вместо тихой выгрузки null.
    if not event.event_code:
        return HttpResponseBadRequest(
            "У мероприятия не задан event_code — экспорт по Integration Spec v1.0 невозможен."
        )

    now = timezone.now()
    last_export = export_service.get_last_export(category)
    lower = last_export.exported_before if last_export else None
    attendees = list(export_service.select_new_attendees(category, lower, now))

    if not attendees:
        return _no_new_response(last_export)

    dir_names = export_service.load_directory_names()
    objects = [export_service.build_export_object(a, dir_names) for a in attendees]

    # Временный файл — на хосте (/tmp), не внутри контейнера (как file_download.py).
    with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Архив пишем ВНЕ транзакции — без долгих блокировок строк во время файлового I/O.
        export_service.write_export_archive(tmp_path, attendees, objects)

        ids = [a.id for a in attendees]
        committed_ids = []
        # Архив отдаём только если ExportLog записан и статусы переведены (всё или ничего).
        with transaction.atomic():
            # D1 (ревью 4.3): блокируем строки и заново проверяем status=ready — защита
            # от гонки двойного экспорта (два POST на одну категорию). Конкурентная
            # транзакция дождётся снятия блокировки и увидит exported → committed_ids пуст.
            committed_ids = list(
                Attendee.objects.select_for_update()
                .filter(id__in=ids, status=AttendeeStatus.READY)
                .order_by("id")
                .values_list("id", flat=True)
            )
            if committed_ids:
                export_log = ExportLog.objects.create(
                    event=event,
                    category=category,
                    exported_before=now,
                    user=request.user,
                    attendee_count=len(committed_ids),
                )
                Attendee.objects.filter(id__in=committed_ids).update(
                    status=AttendeeStatus.EXPORTED
                )
                audit_log(
                    user=request.user,
                    action="export.download",
                    obj_type="Event",
                    obj_id=event_id,
                    ip=request.META.get("REMOTE_ADDR"),
                    extra={
                        "category": category.name,
                        "count": len(committed_ids),
                        "export_log_id": export_log.id,
                    },
                )
            else:
                # Конкурентный экспорт уже забрал записи — фиксировать нечего.
                transaction.set_rollback(True)

        if not committed_ids:
            Path(tmp_path).unlink(missing_ok=True)
            return _no_new_response(last_export)

        # Дашборд статусов кэширует агрегаты (TTL 60с) — после смены ready→exported
        # инвалидируем, иначе оператор видит устаревшие счётчики/флаги (ревью 4.3, P4).
        cache.delete(f"dashboard:event:{event_id}")

        # D2 (ревью 4.3, known-limitation): статусы коммитятся ДО отдачи файла. При обрыве
        # стрима/отмене скачивания записи остаются exported (терминальный), а архив не
        # доставлен — повторно штатно не выгрузить. Риск принят (ручной экспорт
        # Супероператором, низкая частота); при инциденте — ручной reset exported→ready.
        ts = now.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # UTC + Z (Spec v1.0)
        filename = f"export_{event_id}_{_safe_category(category.name)}_{ts}.zip"
        response = FileResponse(
            open(tmp_path, "rb"),
            as_attachment=True,
            filename=filename,
            content_type="application/zip",
        )
        original_close = response.close

        def _close(*args, **kwargs):
            original_close()
            Path(tmp_path).unlink(missing_ok=True)

        response.close = _close
        return response
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise
