"""Story 2.3 — serializers онбординга операторов."""

from django.contrib.auth.models import User
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
