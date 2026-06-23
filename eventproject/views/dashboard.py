"""Story 4.2 — дашборд статусов участников для Супероператора (Django-шаблон, без React).

Strangler Fig: новый файл, legacy не трогаем. RBAC: только superoperator/superuser.
Перф (AC <5с@3000): агрегаты по статусам одним запросом + кэш (Redis) с коротким TTL
(AC допускает обновление по refresh, не real-time).
"""

import logging

from django.contrib.auth.decorators import user_passes_test
from django.core.cache import cache
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from eventproject.models import Attendee, Event, Operator
from eventproject.state_machine import AttendeeStatus

logger = logging.getLogger("eventproject")

# Ограничение списка имён на флаг — защита от гигантской страницы при массовой проблеме.
_FLAG_DISPLAY_CAP = 200
_DASHBOARD_CACHE_TTL = 60  # сек


def _is_superoperator(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return user.operator.role in ("superoperator", "superuser")
    except Operator.DoesNotExist:
        return False


def _name(attendee):
    return " ".join(p for p in (attendee.surname, attendee.firstname) if p)


def _flag_list(qs):
    """{items:[{id,name}], shown, overflow} с ограничением на _FLAG_DISPLAY_CAP."""
    rows = list(qs.only("id", "surname", "firstname")[: _FLAG_DISPLAY_CAP + 1])
    overflow = len(rows) > _FLAG_DISPLAY_CAP
    shown = rows[:_FLAG_DISPLAY_CAP]
    return {
        "items": [{"id": a.id, "name": _name(a)} for a in shown],
        "shown": len(shown),
        "total": len(shown) + (1 if overflow else 0),  # ≥; точное — count() при необходимости
        "overflow": overflow,
    }


def _compute_dashboard(event):
    attendees = Attendee.objects.filter(request__event=event)
    total = attendees.count()

    counts = {
        row["status"]: row["c"]
        for row in attendees.values("status").annotate(c=Count("id"))
    }
    ready = counts.get(AttendeeStatus.READY, 0)
    submitted = counts.get(AttendeeStatus.SUBMITTED, 0)
    in_review = counts.get(AttendeeStatus.IN_REVIEW, 0)
    draft = counts.get(AttendeeStatus.DRAFT, 0)
    exported = counts.get(AttendeeStatus.EXPORTED, 0)

    # Флаги «требуют проверки».
    iin_missing = attendees.filter(is_resident=True, iin__isnull=True)
    photo_missing = attendees.filter(Q(photo="") | Q(photo__isnull=True))
    doc_missing = attendees.filter(Q(docScan="") | Q(docScan__isnull=True))

    flags = [
        {"key": "iin", "label": "ИИН не заполнен / не прошёл валидацию", **_flag_list(iin_missing)},
        {"key": "photo", "label": "Фото не загружено", **_flag_list(photo_missing)},
        {"key": "doc", "label": "Документ не загружен", **_flag_list(doc_missing)},
    ]

    return {
        "total": total,
        "ready": ready,
        "review": submitted + in_review,
        "submitted": submitted,
        "in_review": in_review,
        "draft": draft,
        "exported": exported,
        "all_ready": total > 0 and ready == total,
        "flags": flags,
        "flags_total": sum(f["shown"] for f in flags),
    }


@user_passes_test(_is_superoperator, login_url="/user_login/")
def superoperator_dashboard(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    cache_key = f"dashboard:event:{event_id}"
    data = cache.get(cache_key)
    if data is None:
        data = _compute_dashboard(event)
        cache.set(cache_key, data, _DASHBOARD_CACHE_TTL)
    return render(request, "dashboard.html", {"event": event, **data})
