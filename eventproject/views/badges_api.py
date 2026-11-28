"""Бейджи (второй этап, супероператор и администратор).

* `events/<id>/badge-template/` GET / PUT (multipart: background, layout, name_source) / DELETE;
* `events/<id>/badge-template/background/` — картинка фона;
* `events/<id>/badges/candidates/` — участники для выбора (доступ, печать, фото);
* `events/<id>/badges/preview/` — PNG одной карточки (POST — с несохранённой разметкой);
* `events/<id>/attendees/<aid>/badge.pdf` — один бейдж сразу;
* `events/<id>/badges/` POST — пакетная печать фоновой задачей;
* `jobs/<id>/`, `jobs/<id>/file/` — состояние задачи и готовый PDF.

Печатаются только участники с доступом «разрешён». PDF содержит фото и ФИО, поэтому
лежит вне /media/ и отдаётся только здесь, с проверкой роли.
"""

import io
import json

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from eventproject.audit import audit_log
from eventproject.errors import coded_error
from eventproject.models import Attendee, BadgeTemplate, Event, Job
from eventproject.permissions import IsSuperoperator
from eventproject.services import badges, jobs

BACKGROUND_MAX_BYTES = 5 * 1024 * 1024
BACKGROUND_MAX_PX = 6000


def _ip(request):
    return request.META.get("REMOTE_ADDR", "")


def _name(a):
    return " ".join(p for p in (a.surname, a.firstname) if p) or f"#{a.pk}"


def _template_payload(event, template):
    layout = badges.merged_layout(template.layout if template else None)
    return {
        "event_id": event.id,
        "is_default": template is None,
        "has_background": bool(template and template.background),
        "layout": layout,
        "name_source": template.name_source if template else "ru",
        "updated_at": template.updated_at if template else None,
        "font_ok": badges.font_path() is not None,
    }


def _read_layout(data):
    raw = data.get("layout")
    if raw in (None, ""):
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raise coded_error("badge_layout_invalid", field="layout", reason="JSON")
    try:
        return badges.validate_layout(raw)
    except badges.BadgeError as exc:
        raise coded_error("badge_layout_invalid", field="layout", reason=str(exc))


def _check_background(upload, layout):
    if upload.size > BACKGROUND_MAX_BYTES:
        raise coded_error("badge_background_invalid", field="background", reason="больше 5 МБ")
    try:
        img = Image.open(upload)
        img.verify()
        upload.seek(0)
        img = Image.open(upload)
        fmt, (w, h) = img.format, img.size
    except Exception:
        raise coded_error("badge_background_invalid", field="background", reason="не изображение")
    finally:
        upload.seek(0)
    if fmt not in ("PNG", "JPEG"):
        raise coded_error("badge_background_invalid", field="background", reason="нужен PNG или JPEG")
    cw, ch = badges.card_size(layout)
    if w < cw or h < ch:
        raise coded_error("badge_background_invalid", field="background", reason=f"не меньше {cw}×{ch} пикселей")
    if w > BACKGROUND_MAX_PX or h > BACKGROUND_MAX_PX:
        raise coded_error("badge_background_invalid", field="background", reason="не больше 6000×6000 пикселей")
    if abs((w / h) / (cw / ch) - 1) > 0.02:
        raise coded_error("badge_background_invalid", field="background", reason="пропорции не совпадают с карточкой")


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsSuperoperator])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def badge_template(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    template = BadgeTemplate.objects.filter(event=event).first()
    if request.method == "GET":
        return Response(_template_payload(event, template))
    if request.method == "DELETE":
        if template:
            if template.background:
                template.background.delete(save=False)
            template.delete()
            audit_log(user=request.user, action="badge.template_deleted", obj_type="Event", obj_id=str(event.pk), ip=_ip(request))
        return Response(_template_payload(event, None))

    layout = _read_layout(request.data) or badges.merged_layout(template.layout if template else None)
    name_source = request.data.get("name_source") or (template.name_source if template else "ru")
    if name_source not in ("ru", "latin"):
        raise coded_error("invalid_choice", field="name_source")
    upload = request.FILES.get("background")
    if upload is not None:
        _check_background(upload, layout)
    elif template and template.background and request.data.get("layout"):
        # Разметка привязана к фону: при смене размера карточки старый фон перестаёт подходить.
        with template.background.open("rb") as fh:
            w, h = Image.open(fh).size
        cw, ch = badges.card_size(layout)
        if abs((w / h) / (cw / ch) - 1) > 0.02:
            raise coded_error("badge_background_invalid", field="background", reason="пропорции не совпадают с карточкой")
    with transaction.atomic():
        template, _ = BadgeTemplate.objects.get_or_create(event=event, defaults={"layout": layout})
        template.layout = layout
        template.name_source = name_source
        template.updated_by = request.user
        if upload is not None:
            if template.background:
                template.background.delete(save=False)
            template.background.save(upload.name, upload, save=False)
        if request.data.get("remove_background") in ("1", "true", True) and template.background and upload is None:
            template.background.delete(save=False)
        template.save()
    audit_log(user=request.user, action="badge.template_updated", obj_type="Event", obj_id=str(event.pk), ip=_ip(request))
    return Response(_template_payload(event, template))


@api_view(["GET"])
@permission_classes([IsSuperoperator])
def badge_template_background(request, event_id):
    template = get_object_or_404(BadgeTemplate, event_id=event_id)
    if not template.background:
        return HttpResponse(status=404)
    return FileResponse(template.background.open("rb"), content_type="image/png" if template.background.name.endswith(".png") else "image/jpeg")


@api_view(["GET"])
@permission_classes([IsSuperoperator])
def badge_candidates(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    qs = Attendee.objects.filter(request__event=event).select_related("request").order_by("surname", "firstname", "id")
    access = request.query_params.get("access")
    if access in ("yes", "no", "none"):
        qs = qs.filter(access_status=access)
    printed = request.query_params.get("printed")
    if printed in ("true", "false"):
        qs = qs.filter(badge_printed_at__isnull=(printed == "false"))
    search = (request.query_params.get("search") or "").strip()
    if search:
        for word in search.split():
            qs = qs.filter(Q(surname__icontains=word) | Q(firstname__icontains=word) | Q(transcription__icontains=word))
    rows = [
        {
            "id": a.id,
            "name": _name(a),
            "transcription": a.transcription,
            "request_name": a.request.name,
            "status": a.status,
            "access_status": a.access_status,
            "badge_printed_at": a.badge_printed_at,
            "has_photo": bool(a.photo),
        }
        for a in qs[:5000]
    ]
    return Response({"results": rows, "max_per_job": badges.MAX_BADGES_PER_JOB})


@api_view(["GET", "POST"])
@permission_classes([IsSuperoperator])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def badge_preview(request, event_id):
    """PNG одной карточки. POST {layout, name_source} — предпросмотр несохранённой разметки."""
    event = get_object_or_404(Event, pk=event_id)
    template = BadgeTemplate.objects.filter(event=event).first()
    attendee_id = request.query_params.get("attendee") or request.data.get("attendee")
    qs = Attendee.objects.filter(request__event=event)
    attendee = qs.filter(pk=attendee_id).first() if str(attendee_id or "").isdigit() else qs.order_by("id").first()
    if attendee is None:
        attendee = Attendee(surname="Иванов", firstname="Иван", transcription="IVANOV IVAN")
    layout = _read_layout(request.data) if request.method == "POST" else None
    if request.method == "POST" and request.data.get("name_source") in ("ru", "latin"):
        template = template or BadgeTemplate(event=event)
        template.name_source = request.data["name_source"]
    try:
        png = badges.preview_png(attendee, template, layout)
    except badges.BadgeError as exc:
        raise coded_error("badge_layout_invalid", field="layout", reason=str(exc))
    return HttpResponse(png, content_type="image/png")


@api_view(["GET"])
@permission_classes([IsSuperoperator])
def single_badge(request, event_id, attendee_id):
    """Один бейдж сразу (перепечатка потерянного) — без очереди."""
    attendee = get_object_or_404(Attendee, pk=attendee_id, request__event_id=event_id)
    if attendee.access_status != "yes":
        raise coded_error("badge_not_allowed", field="attendee_ids", names=_name(attendee))
    template = BadgeTemplate.objects.filter(event_id=event_id).first()
    buf = io.BytesIO()
    try:
        badges.build_pdf([attendee], template, buf)
    except badges.BadgeError as exc:
        raise coded_error("badge_layout_invalid", field="layout", reason=str(exc))
    Attendee.objects.filter(pk=attendee.pk).update(badge_printed_at=timezone.now())
    audit_log(
        user=request.user, action="badge.generated", obj_type="Attendee", obj_id=str(attendee.pk), ip=_ip(request),
        extra={"count": 1},
    )
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="badge_{attendee.pk}.pdf"'
    response["Cache-Control"] = "no-store"
    return response


@api_view(["POST"])
@permission_classes([IsSuperoperator])
def create_badge_job(request, event_id):
    """Пакетная печать. Без списка — все с доступом «разрешён», кому бейдж ещё не печатали."""
    event = get_object_or_404(Event, pk=event_id)
    ids = request.data.get("attendee_ids")
    base = Attendee.objects.filter(request__event=event)
    if ids in (None, []):
        chosen = list(base.filter(access_status="yes", badge_printed_at__isnull=True).values_list("pk", flat=True))
    else:
        if not isinstance(ids, list):
            raise coded_error("invalid", field="attendee_ids")
        try:
            ids = [int(x) for x in ids]
        except (TypeError, ValueError):
            raise coded_error("invalid", field="attendee_ids")
        found = {a.pk: a for a in base.filter(pk__in=ids)}
        missing = [i for i in ids if i not in found]
        if missing:
            raise coded_error("not_found", field="attendee_ids")
        refused = [found[i] for i in ids if found[i].access_status != "yes"]
        if refused:
            raise coded_error("badge_not_allowed", field="attendee_ids", names=", ".join(_name(a) for a in refused[:20]))
        chosen = ids
    if not chosen:
        raise coded_error("badge_nothing_to_print", field="attendee_ids")
    if len(chosen) > badges.MAX_BADGES_PER_JOB:
        raise coded_error("badge_limit", field="attendee_ids", limit=badges.MAX_BADGES_PER_JOB)
    with transaction.atomic():
        job = jobs.enqueue("badge_pdf", {"event_id": event.pk, "attendee_ids": chosen}, user=request.user)
    cache.delete(f"dashboard:event:{event.pk}")
    return Response(_job_payload(Job.objects.get(pk=job.pk)), status=status.HTTP_202_ACCEPTED)


def _job_payload(job):
    return {
        "id": job.pk,
        "type": job.type,
        "status": job.status,
        "progress": job.progress,
        "result": job.result,
        "error": job.error if job.status == "failed" else "",
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "has_file": bool(job.file_path) and job.status == "completed",
    }


@api_view(["GET"])
@permission_classes([IsSuperoperator])
def job_detail(request, job_id):
    return Response(_job_payload(get_object_or_404(Job, pk=job_id)))


@api_view(["GET"])
@permission_classes([IsSuperoperator])
def job_file(request, job_id):
    job = get_object_or_404(Job, pk=job_id, status="completed")
    if not job.file_path:
        return HttpResponse(status=404)
    try:
        fh = open(job.file_path, "rb")
    except OSError:
        return HttpResponse(status=404)
    audit_log(user=request.user, action="badge.downloaded", obj_type="Job", obj_id=str(job.pk), ip=_ip(request))
    name = (job.result or {}).get("file_name") or f"badges_{job.pk}.pdf"
    response = FileResponse(fh, content_type="application/pdf", as_attachment=True, filename=name)
    response["Cache-Control"] = "no-store"
    return response
