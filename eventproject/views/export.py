"""Story 4.3 + этап C — пакеты delta-экспорта (Супероператор).

Три отдельных действия:
- POST `export_delta/<event_id>/<request_id>/` формирует пакет из всех `ready`-
  участников категории: манифест (SHA-256, размер и CRC-32 каждого элемента,
  SHA-256 всего архива), ExportLog с package_id и составом, перевод ready →
  exported и audit_log — атомарно. Затем 303 на выдачу файла пакета.
- GET/POST `export_package/<package_id>/download/` отдаёт файл пакета. Архив
  собирается потоком из БД и файлов (`services/zipstream.py`): без временного
  файла и без копии на сервере, с заранее известным размером и докачкой (Range).
  Если данные расходятся с манифестом, выдача блокируется (409); расхождение,
  найденное уже во время передачи, обрывает поток — под тем же идентификатором
  получатель не получит другое содержимое.
- POST `export_package/<package_id>/acknowledge/` фиксирует подтверждение
  получателя. Формирование и выдача файла подтверждением не считаются.

Большие пакеты (гигабайты): ответ идёт блоками, Gunicorn работает потоками
(gthread — длинная передача не убивает воркер), nginx для этих путей не
буферизует ответ и ждёт дольше (frontend/release.nginx.conf).
"""

import logging
import re
import uuid
from datetime import timezone as dt_timezone

from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import content_disposition_header, http_date, quote_etag
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST

from eventproject.audit import audit_log
from eventproject.models import Attendee, Event, ExportLog, Request
from eventproject.services import export as export_service
from eventproject.services import zipstream
from eventproject.state_machine import AttendeeStatus
from eventproject.views.dashboard import _is_superoperator

logger = logging.getLogger(__name__)


def _safe_category(name):
    """Безопасное имя категории для имени файла архива."""
    cleaned = re.sub(r"[^\w.-]+", "_", name or "", flags=re.UNICODE).strip("_")
    return cleaned or "all"


def _package_filename(event_id, category, packaged_at, package_id):
    """Integration Spec v1.1: export_<event_id>_<category>_<timestamp>_<package8>.zip.

    The first 8 hex digits of package_id keep names distinct when two packages of
    one category are formed within the same second.
    """
    ts = packaged_at.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"export_{event_id}_{_safe_category(category.name)}_{ts}_{package_id.hex[:8]}.zip"


def _text(message, status=200):
    return HttpResponse(message, status=status, content_type="text/plain; charset=utf-8")


def _no_new_response(last_export):
    """Сообщение AC-5: новых записей нет (ZIP/ExportLog/смены статусов не происходит)."""
    if last_export:
        when = timezone.localtime(last_export.exported_before).strftime("%d.%m.%Y %H:%M")
        msg = f"Нет новых записей с момента последнего экспорта ({when})"
    else:
        msg = "Нет записей со статусом «ready» для экспорта в этой категории"
    return _text(msg)


def _guard(request):
    """None, если доступ есть; иначе ответ для анонима. Нет прав → 403."""
    # Аноним → на логин (302); аутентифицированный без прав → 403 (как дашборд 4.2).
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url="/user_login/")
    if not _is_superoperator(request.user):
        raise PermissionDenied
    return None


def _ip(request):
    return request.META.get("REMOTE_ADDR")


def _refuse(request, export_log, differences):
    audit_log(
        user=request.user,
        action="export.redownload_refused",
        obj_type="ExportLog",
        obj_id=export_log.id,
        ip=_ip(request),
        extra={"package_id": str(export_log.package_id), "changed": differences[:50]},
    )
    listed = ", ".join(differences[:10]) + (" …" if len(differences) > 10 else "")
    return _text(
        "Данные пакета изменились с момента выгрузки, повторная выдача заблокирована, "
        "чтобы под тем же идентификатором не передать другое содержимое. "
        f"Изменились: {listed or 'файлы участников'}.",
        status=409,
    )


def _guarded_stream(chunks, request, export_log):
    """Поток архива; расхождение посреди передачи → запись в журнал и обрыв."""
    try:
        yield from chunks
    except zipstream.SourceChanged as exc:
        logger.warning("Export package stream aborted: source changed")
        audit_log(
            user=request.user,
            action="export.redownload_refused",
            obj_type="ExportLog",
            obj_id=export_log.id,
            ip=_ip(request),
            extra={
                "package_id": str(export_log.package_id),
                "changed": [str(exc.args[0])],
                "mid_stream": True,
            },
        )
        raise


@require_POST
@csrf_protect
def export_delta(request, event_id, request_id):
    denied = _guard(request)
    if denied:
        return denied

    event = get_object_or_404(Event, pk=event_id)
    category = get_object_or_404(Request, pk=request_id, event=event)

    # D4 (ревью 4.3): event_code обязателен по контракту v1.0 (required, nullable=false).
    # Без него attendees.json был бы невалиден — fail-fast вместо тихой выгрузки null.
    if not event.event_code:
        return HttpResponseBadRequest(
            "У мероприятия не задан event_code — экспорт по Integration Spec v1.0 невозможен."
        )

    now = timezone.now()
    attendees = list(export_service.select_ready_attendees(category))
    if not attendees:
        return _no_new_response(export_service.get_last_export(category))

    dir_names = export_service.load_directory_names()
    pairs = export_service.prepare_package_objects(attendees, dir_names)
    ids = [attendee.pk for attendee in attendees]
    package_id = uuid.uuid4()
    filename = _package_filename(event_id, category, now, package_id)

    # Файлы читаются вне блокировки: на больших пакетах это занимает время.
    try:
        manifest, stamps = export_service.describe_package(pairs)
        archive_sha256 = export_service.stream_sha256(export_service.package_stream(pairs, manifest, now))
    except (export_service.ExportSourceChanged, export_service.PackageMismatch):
        return _text("Файл участника изменился во время выгрузки. Повторите экспорт.", status=409)

    with transaction.atomic():
        # Lock in the same ID order as the archive and recheck membership.
        committed_ids = list(
            Attendee.objects.filter(request=category, status=AttendeeStatus.READY, pk__in=ids)
            .order_by("id").select_for_update().values_list("pk", flat=True)
        )
        if committed_ids != ids:
            return _text("Состав выгрузки изменился. Повторите экспорт.", status=409)
        # Under the lock, the rows must still describe what the archive contains.
        current = export_service.prepare_package_objects(
            export_service.select_ready_attendees(category).filter(pk__in=ids), dir_names,
        )
        current_json = export_service.attendees_json_bytes([obj for _, obj in current])
        if export_service.sha256_hex(current_json) != manifest["attendees.json"]["sha256"]:
            return _text("Данные участников изменились во время выгрузки. Повторите экспорт.", status=409)
        if not export_service.files_unchanged(stamps):
            return _text("Файл участника изменился во время выгрузки. Повторите экспорт.", status=409)

        export_log = ExportLog.objects.create(
            event=event,
            category=category,
            exported_before=now,
            user=request.user,
            attendee_count=len(ids),
            package_id=package_id,
            attendee_ids=ids,
            manifest=manifest,
            archive_name=filename,
            archive_sha256=archive_sha256,
        )
        Attendee.objects.filter(pk__in=ids).update(status=AttendeeStatus.EXPORTED)
        audit_log(
            user=request.user,
            action="export.download",
            obj_type="Event",
            obj_id=event_id,
            ip=_ip(request),
            extra={
                "category": category.name,
                "count": len(ids),
                "export_log_id": export_log.id,
                "package_id": str(export_log.package_id),
            },
        )
        transaction.on_commit(lambda: cache.delete(f"dashboard:event:{event_id}"), robust=True)

    # Файл выдаётся отдельным GET: после обрыва браузер докачает его с места обрыва.
    response = redirect("export_package_download", package_id=export_log.package_id)
    response.status_code = 303
    response["X-Export-Package-Id"] = str(export_log.package_id)
    response["X-Export-Archive-SHA256"] = archive_sha256
    return response


@require_http_methods(["GET", "POST"])
@csrf_protect
def export_package_download(request, package_id):
    denied = _guard(request)
    if denied:
        return denied

    export_log = get_object_or_404(ExportLog, package_id=package_id)
    if not export_log.can_redownload:
        return _text(
            "Пакет сформирован до введения повторной выдачи: его состав не записан. "
            "Повторная выдача невозможна.",
            status=410,
        )

    ids = list(export_log.attendee_ids)
    attendees = list(
        Attendee.objects.filter(pk__in=ids).select_related("request__event", "category").order_by("id")
    )
    if [attendee.pk for attendee in attendees] != ids:
        return _text("Часть участников пакета удалена. Повторная выдача невозможна.", status=409)

    pairs = export_service.prepare_package_objects(attendees)
    try:
        stream = export_service.package_stream(pairs, export_log.manifest, export_log.exported_before)
    except export_service.PackageMismatch as exc:
        return _refuse(request, export_log, list(exc.args[0]))

    etag = quote_etag(export_log.archive_sha256)
    window = None
    if_range = request.headers.get("If-Range")
    if if_range is None or if_range == etag:
        try:
            window = zipstream.parse_range(request.headers.get("Range"), stream.size)
        except zipstream.RangeNotSatisfiable:
            response = _text("Запрошенный диапазон вне архива.", status=416)
            response["Content-Range"] = f"bytes */{stream.size}"
            return response

    start, end = window or (0, stream.size)
    extra = {"package_id": str(export_log.package_id), "count": len(ids)}
    if window:
        extra["range"] = [start, end - 1]
    audit_log(
        user=request.user,
        action="export.redownload",
        obj_type="ExportLog",
        obj_id=export_log.id,
        ip=_ip(request),
        extra=extra,
    )

    response = StreamingHttpResponse(
        _guarded_stream(stream.iter_bytes(start, end), request, export_log),
        status=206 if window else 200,
        content_type="application/zip",
    )
    response["Content-Length"] = str(end - start)
    if window:
        response["Content-Range"] = f"bytes {start}-{end - 1}/{stream.size}"
    response["Accept-Ranges"] = "bytes"
    response["ETag"] = etag
    response["Last-Modified"] = http_date(export_log.exported_before.timestamp())
    response["Content-Disposition"] = content_disposition_header(True, export_log.archive_name)
    response["Cache-Control"] = "private, no-store"
    response["X-Export-Package-Id"] = str(export_log.package_id)
    response["X-Export-Archive-SHA256"] = export_log.archive_sha256
    return response


@require_POST
@csrf_protect
def export_package_acknowledge(request, package_id):
    denied = _guard(request)
    if denied:
        return denied

    with transaction.atomic():
        export_log = get_object_or_404(ExportLog.objects.select_for_update(), package_id=package_id)
        if export_log.acknowledged_at is None:
            export_log.acknowledged_at = timezone.now()
            export_log.acknowledged_by = request.user
            export_log.save(update_fields=["acknowledged_at", "acknowledged_by"])
            audit_log(
                user=request.user,
                action="export.acknowledge",
                obj_type="ExportLog",
                obj_id=export_log.id,
                ip=_ip(request),
                extra={"package_id": str(export_log.package_id)},
            )
    return redirect("superoperator_dashboard", event_id=export_log.event_id)
