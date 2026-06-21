from rest_framework import serializers
from eventproject.models import Event, Category


class CategorySerializer(serializers.ModelSerializer):
    attendee_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "attendee_count"]

    def get_attendee_count(self, obj):
        # Если queryset аннотирован (_attendee_count из Prefetch) — берём из аннотации,
        # чтобы не плодить N+1 COUNT-запросов на списке events.
        annotated = getattr(obj, "_attendee_count", None)
        if annotated is not None:
            return annotated
        # related_name="attendees" из модели Attendee
        return obj.attendees.count()

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Название категории не может быть пустым.")
        return value


class EventSerializer(serializers.ModelSerializer):
    categories = CategorySerializer(many=True, read_only=True)
    # Поля модели сделаны nullable для legacy-совместимости, поэтому минимальный
    # контракт создания мероприятия требуем явно на уровне API (AC-1).
    title = serializers.CharField(required=True, allow_blank=False, max_length=255)
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)

    class Meta:
        model = Event
        fields = ["id", "title", "start_date", "end_date", "description", "categories", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "Дата окончания не может быть раньше даты начала."}
            )
        return attrs
