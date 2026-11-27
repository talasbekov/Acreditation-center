"""Этап C — очередь проверки участников для супероператора (Django-шаблон).

GET  /review/<event_id>/                         — участники мероприятия на проверке;
POST /review/attendee/<id>/start|approve|return/ — решения проверяющего.

Переходы выполняет services.lifecycle; здесь только права, ввод и ответ.
Открытие страницы ничего не меняет.
"""

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from directories.models import Country, DocumentType
from eventproject.models import Attendee, Event
from eventproject.services import lifecycle
from eventproject.state_machine import AttendeeStatus

_QUEUE_STATUSES = (AttendeeStatus.SUBMITTED, AttendeeStatus.IN_REVIEW)
_QUEUE_CAP = 200

_ACTIONS = {
    "start": lifecycle.start_review,
    "approve": lifecycle.approve,
}

_DONE = {
    "start": "взят(а) на проверку",
    "approve": "допущен(а)",
    "return": "возвращен(а) оператору",
}


def _guard(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url="/user_login/")
    if not lifecycle.is_reviewer(request.user):
        raise PermissionDenied
    return None


@require_GET
def review_queue(request, event_id):
    denied = _guard(request)
    if denied:
        return denied
    event = get_object_or_404(Event, pk=event_id)
    queue = (
        Attendee.objects.filter(request__event=event, status__in=_QUEUE_STATUSES)
        .select_related("request", "request__created_by__user", "category", "reviewed_by")
        .order_by("request_id", "id")
    )
    total = queue.count()
    countries = {c.country_code: c.name_rus for c in Country.objects.all()}
    doc_types = {d.doc_code: d.name_rus for d in DocumentType.objects.all()}
    items = [
        {
            "a": a,
            "country": countries.get(a.countryId, a.countryId),
            "doc_type": doc_types.get(a.docTypeId, a.docTypeId),
            "operator": a.request.created_by.user.get_full_name() or a.request.created_by.user.username,
        }
        for a in queue[:_QUEUE_CAP]
    ]
    summary = lifecycle.status_summary(Attendee.objects.filter(request__event=event).only("status", "review_comment"))
    return render(request, "review.html", {
        "event": event, "section": "review", "items": items, "total": total, "overflow": total > _QUEUE_CAP,
        "summary": summary, "max_reason": lifecycle.RETURN_REASON_MAX,
    })


@require_POST
@csrf_protect
def review_decision(request, attendee_id, decision):
    denied = _guard(request)
    if denied:
        return denied
    if decision not in _DONE:
        raise Http404
    attendee = get_object_or_404(Attendee.objects.select_related("request"), pk=attendee_id)
    event_id = attendee.request.event_id
    ip = request.META.get("REMOTE_ADDR")
    try:
        if decision == "return":
            lifecycle.return_for_changes(attendee.pk, request.user, request.POST.get("reason", ""), ip)
        else:
            _ACTIONS[decision](attendee.pk, request.user, ip)
    except lifecycle.LifecycleError as exc:
        messages.error(request, f"{attendee.surname} {attendee.firstname}: {exc.message}")
    else:
        messages.success(request, f"{attendee.surname} {attendee.firstname} {_DONE[decision]}")
        cache.delete(f"dashboard:event:{event_id}")
    return redirect("review_queue", event_id=event_id)
