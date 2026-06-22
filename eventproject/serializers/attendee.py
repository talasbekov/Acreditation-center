"""Story 3.4 — DRF serializer участника.

Валидация ИИН/резидентства делегируется единым источникам:
`validators/residency.resolve_residency` (→ `validators/iin.validate_iin`).
Дедуп ИИН в рамках мероприятия — `validators/iin.event_has_iin_duplicate`.
"""

from rest_framework import serializers

from eventproject.models import Attendee, Request
from eventproject.validators.iin import event_has_iin_duplicate
from eventproject.validators.residency import resolve_residency


class AttendeeSerializer(serializers.ModelSerializer):
    # PK-поля и iin объявлены явно (iin — EncryptedCharField, не полагаемся на
    # авто-маппинг DRF).
    request = serializers.PrimaryKeyRelatedField(queryset=Request.objects.all())
    iin = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=12
    )

    class Meta:
        model = Attendee
        fields = [
            "id",
            "surname",
            "firstname",
            "patronymic",
            "birthDate",
            "post",
            "countryId",
            "docTypeId",
            "docSeries",
            "iin",
            "docNumber",
            "docBegin",
            "docEnd",
            "docIssue",
            "sexId",
            "visitObjects",
            "transcription",
            "request",
            "category",
            "dateEnd",
            "is_resident",
            "status",
            "dateAdd",
        ]
        # Выставляются сервером/логикой, не клиентом.
        read_only_fields = ["id", "is_resident", "status", "dateAdd"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        def current(field):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, None)

        country_id = current("countryId")
        iin = current("iin")
        birth_date = current("birthDate")

        # Residency + ИИН (Story 3.1/3.2): обязательность/валидность/нормализация.
        result = resolve_residency(country_id, iin, birth_date)
        if result.error:
            raise serializers.ValidationError({"iin": result.error})
        attrs["is_resident"] = result.is_resident
        attrs["iin"] = result.iin  # None для нерезидента

        # Дедуп ИИН резидента РК в рамках мероприятия (паритет legacy).
        if result.is_resident and result.iin:
            req = current("request")
            if req is not None:
                existing = Attendee.objects.filter(request__event=req.event)
                exclude_pk = instance.pk if instance is not None else None
                if event_has_iin_duplicate(existing, result.iin, exclude_pk=exclude_pk):
                    raise serializers.ValidationError(
                        {"iin": "Участник с этим ИИН уже добавлен в это мероприятие."}
                    )
        return attrs
