"""Story 2.3 — serializers онбординга операторов.

Story 2.4 — serializers реестра операторов и истории доступа (внизу файла).
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from eventproject.models import Category, Event, Operator


class OperatorCreateSerializer(serializers.Serializer):
    """Входные данные для создания оператора Супероператором (AC-1).

    Username и пароль генерируются на сервере (см. services.operator_onboarding),
    поэтому здесь они не принимаются.
    """

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    patronymic = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default=""
    )
    email = serializers.EmailField()
    event_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    category_id = serializers.IntegerField(required=False, allow_null=True, default=None)

    def validate_event_ids(self, value):
        if not value:
            return value
        existing = set(
            Event.objects.filter(id__in=value).values_list("id", flat=True)
        )
        missing = [eid for eid in value if eid not in existing]
        if missing:
            raise serializers.ValidationError(
                f"Мероприятия не найдены: {missing}"
            )
        return value

    def validate_category_id(self, value):
        if value is not None and not Category.objects.filter(id=value).exists():
            raise serializers.ValidationError("Категория не найдена.")
        return value

    def validate_email(self, value):
        # Уникальность email: иначе повторный онбординг создаёт shadow-аккаунты
        # с тем же email, но разными логинами/паролями (review finding).
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Пользователь с таким email уже существует."
            )
        return value


class OperatorReadSerializer(serializers.ModelSerializer):
    """Ответ при создании/ресенде: данные оператора без секретов."""

    id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    event_ids = serializers.SerializerMethodField()
    category_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Operator
        fields = [
            "id",
            "user_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "patronymic",
            "role",
            "email_status",
            "credentials_sent_at",
            "force_password_change",
            "event_ids",
            "category_id",
        ]

    def get_event_ids(self, obj):
        return list(obj.events.values_list("id", flat=True))


# ───────────────────────────── Story 2.4 ─────────────────────────────


_EMAIL_STATUS_DISPLAY = {
    "pending": "Не отправлено",
    "sent": "Отправлено",
    "error": "Ошибка",
}


class OperatorRegistryListSerializer(serializers.ModelSerializer):
    """Реестр операторов (list) — AC-1/AC-2/AC-5.

    Отдельный сериализатор: НЕ меняем OperatorReadSerializer (контракт 2.3).
    Все «дата создания / последний вход / активность» берутся из User.
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    full_name = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    email_status_display = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(source="user.date_joined", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    inactivity_warning = serializers.SerializerMethodField()

    class Meta:
        model = Operator
        fields = [
            "id",
            "user_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "patronymic",
            "full_name",
            "role",
            "events",
            "category",
            "email_status",
            "email_status_display",
            "date_joined",
            "last_login",
            "is_active",
            "inactivity_warning",
        ]

    def get_full_name(self, obj):
        parts = [obj.user.last_name, obj.user.first_name, obj.patronymic]
        return " ".join(p for p in parts if p).strip()

    def get_events(self, obj):
        return [
            {"id": e.id, "title": (e.title or e.name_rus or f"Event {e.id}")}
            for e in obj.events.all()
        ]

    def get_category(self, obj):
        if obj.category_id is None:
            return None
        return {"id": obj.category.id, "name": obj.category.name}

    def get_email_status_display(self, obj):
        return _EMAIL_STATUS_DISPLAY.get(obj.email_status, obj.email_status)

    def get_inactivity_warning(self, obj):
        # Никогда не входивший оператор → предупреждение (AC-5).
        last = obj.user.last_login
        if last is None:
            return True
        threshold = getattr(settings, "OPERATOR_INACTIVITY_THRESHOLD_DAYS", 30)
        return last < timezone.now() - timedelta(days=threshold)


class OperatorRegistryDetailSerializer(OperatorRegistryListSerializer):
    """Детальный вид оператора с историей доступа (AC-3)."""

    created_at = serializers.DateTimeField(source="user.date_joined", read_only=True)
    first_login_at = serializers.SerializerMethodField()
    password_changes = serializers.SerializerMethodField()
    access_events = serializers.SerializerMethodField()

    class Meta(OperatorRegistryListSerializer.Meta):
        fields = OperatorRegistryListSerializer.Meta.fields + [
            "created_at",
            "first_login_at",
            "password_changes",
            "access_events",
        ]

    def get_first_login_at(self, obj):
        ev = (
            obj.access_events.filter(event_type="login")
            .order_by("timestamp")
            .first()
        )
        return ev.timestamp if ev else None

    def get_password_changes(self, obj):
        return [
            e.timestamp
            for e in obj.access_events.filter(event_type="password_changed").order_by(
                "-timestamp"
            )
        ]

    def get_access_events(self, obj):
        # Meta.ordering = -timestamp → последние события первыми. Ограничиваем 50.
        return [
            {
                "event_type": e.event_type,
                "timestamp": e.timestamp,
                "actor_username": (e.actor.username if e.actor_id else None),
                "ip": e.ip,
            }
            for e in obj.access_events.all()[:50]
        ]
