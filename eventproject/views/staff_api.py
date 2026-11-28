"""Страницы супероператора для Next.js: `/api/v1/staff/…`.

Повторяют HTML-страницы этапа C (только супероператор и суперпользователь):

* `superoperator_dashboard` → `GET staff/events/<id>/dashboard/` — те же счётчики,
  флаги, заявки для выгрузки и пакеты; тот же кэш на 60 секунд;
* `review_queue` → `GET staff/events/<id>/review/`;
* `review_decision` → `POST staff/attendees/<id>/<start|approve|return>/` — те же
  переходы через services.lifecycle, те же тексты и сброс кэша дашборда.

Сами выгрузки (формирование пакета, повторная выдача, подтверждение получателя)
остаются адресами Django `/export_delta/…` и `/export_package/…`.
"""

from datetime import date, timedelta

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from directories.models import Country, DocumentType
from eventproject.models import Attendee, Event, ExportLog, Request
from eventproject.permissions import IsSuperoperator
from eventproject.serializers.event import event_brief
from eventproject.services import lifecycle
from eventproject.views.dashboard import _DASHBOARD_CACHE_TTL, _PACKAGE_DISPLAY_CAP, _compute_dashboard
from eventproject.views.review import _DONE, _QUEUE_CAP, _QUEUE_STATUSES

STAFF_DAYS = 900


@api_view(["GET"])
@permission_classes([IsSuperoperator])
def staff_events(request):
    """Мероприятия для перехода к проверке и выгрузке (идут и предстоят, 900 дней)."""
    start = date.today()
    events = Event.objects.filter(date_end__range=[start, start + timedelta(days=STAFF_DAYS)]).order_by("date_start")
    return Response({"events": [event_brief(e) for e in events]})


def _package_row(pkg):
    return {
        "package_id": str(pkg.package_id),
        "category": pkg.category.name if pkg.category_id else None,
        "exported_before": pkg.exported_before,
        "attendee_count": pkg.attendee_count,
        "archive_name": pkg.archive_name or "",
        "acknowledged_at": pkg.acknowledged_at,
        "acknowledged_by": pkg.acknowledged_by.username if pkg.acknowledged_by_id else None,
        "can_redownload": bool(pkg.can_redownload),
    }


@api_view(["GET"])
@permission_classes([IsSuperoperator])
def staff_dashboard(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    cache_key = f"dashboard:event:{event_id}"
    data = cache.get(cache_key)
    if data is None:
        data = _compute_dashboard(event)
        cache.set(cache_key, data, _DASHBOARD_CACHE_TTL)
    categories = Request.objects.filter(event=event).order_by("name")
    packages = (
        ExportLog.objects.filter(event=event)
        .select_related("category", "user", "acknowledged_by")
        .order_by("-exported_before", "-id")[:_PACKAGE_DISPLAY_CAP]
    )
    return Response(
        {
            "event": event_brief(event),
            **data,
            "categories": [{"id": r.id, "name": r.name, "status": r.status} for r in categories],
            "packages": [_package_row(p) for p in packages],
        }
    )


@api_view(["GET"])
@permission_classes([IsSuperoperator])
def staff_review(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    queue = (
        Attendee.objects.filter(request__event=event, status__in=_QUEUE_STATUSES)
        .select_related("request", "request__created_by__user")
        .order_by("request_id", "id")
    )
    total = queue.count()
    countries = {c.country_code: c.name_rus for c in Country.objects.all()}
    doc_types = {d.doc_code: d.name_rus for d in DocumentType.objects.all()}
    items = []
    for a in queue[:_QUEUE_CAP]:
        creator = a.request.created_by.user
        items.append(
            {
                "id": a.id,
                "surname": a.surname,
                "firstname": a.firstname,
                "patronymic": a.patronymic or "",
                "status": a.status,
                "transcription": a.transcription,
                "birthDate": a.birthDate,
                "country": countries.get(a.countryId, a.countryId),
                "doc_type": doc_types.get(a.docTypeId, a.docTypeId),
                "docSeries": a.docSeries or "",
                "docNumber": a.docNumber or "",
                "docEnd": a.docEnd,
                "post": a.post,
                "visitObjects": a.visitObjects,
                "photo": a.photo.url if a.photo else None,
                "docScan": a.docScan.url if a.docScan else None,
                "request_name": a.request.name,
                "operator": creator.get_full_name() or creator.username,
            }
        )
    summary = lifecycle.status_summary(Attendee.objects.filter(request__event=event).only("status", "review_comment"))
    return Response(
        {
            "event": event_brief(event),
            "items": items,
            "total": total,
            "overflow": total > _QUEUE_CAP,
            "summary": summary,
            "max_reason": lifecycle.RETURN_REASON_MAX,
        }
    )


_ACTIONS = {"start": lifecycle.start_review, "approve": lifecycle.approve}


@api_view(["POST"])
@permission_classes([IsSuperoperator])
def staff_decision(request, attendee_id, decision):
    if decision not in _DONE:
        return Response({"type": "not_found", "detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
    attendee = get_object_or_404(Attendee.objects.select_related("request"), pk=attendee_id)
    event_id = attendee.request.event_id
    ip = request.META.get("REMOTE_ADDR")
    name = f"{attendee.surname} {attendee.firstname}"
    try:
        if decision == "return":
            reason = request.data.get("reason", "")
            lifecycle.return_for_changes(attendee.pk, request.user, reason if isinstance(reason, str) else "", ip)
        else:
            _ACTIONS[decision](attendee.pk, request.user, ip)
    except lifecycle.LifecycleError as exc:
        return Response(
            {"type": "decision_failed", "field": None, "params": {}, "detail": f"{name}: {exc.message}"},
            status=status.HTTP_409_CONFLICT if exc.conflict else status.HTTP_400_BAD_REQUEST,
        )
    cache.delete(f"dashboard:event:{event_id}")
    return Response({"message": f"{name} {_DONE[decision]}"})
