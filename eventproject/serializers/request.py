from rest_framework import serializers

from eventproject.models import Request
from eventproject.serializers.event import event_brief


class RequestSerializer(serializers.ModelSerializer):
    """FE-1 — лёгкий read-only сериализатор Request для селектора «категории».

    `Attendee.request` — FK на Request; форма участника выбирает Request из
    RBAC-scoped списка. Отдаём минимум для `<select>`: id + имя + контекст события.
    """

    event_id = serializers.IntegerField(source="event.id", read_only=True)
    event_name = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = ["id", "name", "event_id", "event_name", "status", "date_created"]

    def get_event_name(self, obj):
        # title/name_rus nullable (legacy) → берём первое заполненное, иначе fallback.
        ev = obj.event
        return ev.title or ev.name_rus or f"Мероприятие {obj.event_id}"


def request_payload(req, request, with_attendees=False):
    """Заявка для страницы заявки Next.js (как контекст `request.html`)."""
    from eventproject.services import lifecycle
    from eventproject.views.request_api import attendee_rows

    operator = req.created_by
    data = {
        "id": req.id,
        "name": req.name,
        "status": req.status,
        "date_created": req.date_created,
        "registration_time": req.registration_time,
        "event": event_brief(req.event),
        "created_by": {
            "id": operator.id,
            "username": operator.user.username,
            "full_name": operator.user.get_full_name() or operator.user.username,
        },
        "can_add": lifecycle.can_add_to(req),
        "can_preview": lifecycle.can_preview(req),
    }
    if with_attendees:
        data["attendees"] = attendee_rows(req, request)
    return data
