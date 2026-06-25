from rest_framework import serializers

from eventproject.models import Request


class RequestSerializer(serializers.ModelSerializer):
    """FE-1 — лёгкий read-only сериализатор Request для селектора «категории».

    `Attendee.request` — FK на Request; форма участника выбирает Request из
    RBAC-scoped списка. Отдаём минимум для `<select>`: id + имя + контекст события.
    """

    event_id = serializers.IntegerField(source="event.id", read_only=True)
    event_name = serializers.SerializerMethodField()

    class Meta:
        model = Request
        fields = ["id", "name", "event_id", "event_name"]

    def get_event_name(self, obj):
        # title/name_rus nullable (legacy) → берём первое заполненное, иначе fallback.
        ev = obj.event
        return ev.title or ev.name_rus or f"Мероприятие {obj.event_id}"
