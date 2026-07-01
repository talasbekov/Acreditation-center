"""Story fe-3.1 — DTO-сериализатор очереди проверки (замороженный контракт 3.2-3.7).

snake_case (конвенция 4-1 integration-spec: reference-FK → `*_id` + `*_name` парой).
Сырой ИИН не отдаётся — только `iin_masked` (mask_iin, как AttendeeListSerializer).
Поля `last_return_reason`/`return_count` несут контракт для continuity (3.7); их
реальный источник придёт из 3.5/3.6/3.7 (FSM «Возвращена» + audit), пока — null/0.
"""

from rest_framework import serializers

from eventproject.models import Attendee
from eventproject.problem_flags import sanitize_problem_flags
from eventproject.validators.iin import mask_iin


class ReviewQueueSerializer(serializers.ModelSerializer):
    """DTO элемента очереди проверки. Read-only (ReviewQueueViewSet)."""

    full_name = serializers.SerializerMethodField()
    iin_masked = serializers.SerializerMethodField()
    problem_flags = serializers.SerializerMethodField()
    sub_event_id = serializers.SerializerMethodField()
    sub_event_name = serializers.SerializerMethodField()
    sub_event_names = serializers.SerializerMethodField()
    last_return_reason = serializers.SerializerMethodField()
    return_count = serializers.SerializerMethodField()

    class Meta:
        model = Attendee
        fields = [
            "id",
            "full_name",
            "iin_masked",
            "status",
            "sub_event_id",
            "sub_event_name",
            "sub_event_names",
            "problem_flags",
            "last_return_reason",
            "return_count",
        ]

    def get_full_name(self, obj):
        # ФИО НЕ локализуется (UX-DR3). Отчество опционально.
        parts = [obj.surname, obj.firstname, obj.patronymic]
        return " ".join(p for p in parts if p).strip()

    def get_iin_masked(self, obj):
        return mask_iin(obj.iin)

    def get_problem_flags(self, obj):
        # Закрытый набор enforced на сериализации: битое/legacy хранимое значение НЕ
        # протекает наружу (иначе zod-схема фронта отвергла бы весь ответ — one-bad-row
        # outage всей страницы очереди).
        return sanitize_problem_flags(obj.problem_flags)

    def get_sub_event_id(self, obj):
        # N:1 (hd-5.1): leaf-Event заявки = request.event_id. Nullable защитно.
        return obj.request.event_id if obj.request_id else None

    def get_sub_event_name(self, obj):
        if not obj.request_id:
            return None
        event = obj.request.event
        # name_rus — ru/legacy fallback (frozen fe-3.1); трилингв-триплет — sub_event_names (fe-1.5).
        return event.name_rus or event.title or event.event_code or None

    def get_sub_event_names(self, obj):
        # fe-1.5 (AC4, Q3): трилингв-триплет {ru,kz,en} для клиент-локаль-выбора (React
        # pickLocalizedName). Аддитивно к sub_event_name (frozen fe-3.1 = ru fallback, НЕ трогаем).
        # Nullable-safe: нет request → null (как sub_event_name). Request.event — non-null FK.
        if not obj.request_id:
            return None
        event = obj.request.event
        return {"ru": event.name_rus, "kz": event.name_kaz, "en": event.name_eng}

    def get_last_return_reason(self, obj):
        # Story fe-3.5: причина последнего возврата (хранимое поле Attendee, пишет return-экшен).
        return obj.last_return_reason

    def get_return_count(self, obj):
        # Story fe-3.5: счётчик возвратов (хранимое поле, инкремент return-экшеном).
        return obj.return_count


class ReviewQueueDetailSerializer(ReviewQueueSerializer):
    """Story fe-3.3 — DTO ЭКРАНА ДЕТАЛЕЙ заявки (retrieve-only).

    Расширяет замороженный список (ReviewQueueSerializer) полями, нужными экрану
    review: ссылки на фото/скан документа + identity-поля. ИИН ОСТАЁТСЯ
    маскированным (наследуется `iin_masked`) — сырой ИИН не отдаётся (инвариант
    fe-3.1). Поля `country`/`post`/`transcription` — хранимые значения как есть
    (резолюция кода страны → имя = follow-up); `submitted_at`/`pdn_consent`
    отсутствуют в модели Attendee → НЕ выдуманы (out-of-scope до hardening).
    """

    photo = serializers.SerializerMethodField()
    doc_scan = serializers.SerializerMethodField()
    birth_date = serializers.DateField(source="birthDate", allow_null=True)
    is_resident = serializers.BooleanField()
    country = serializers.CharField(source="countryId")
    post = serializers.CharField()
    transcription = serializers.CharField()
    # fe-3.3 review (Erda 2026-06-30): «Тип документа» из мокапа. `docTypeId` —
    # хранимый CharField-код (нет таблицы DocType/choices → нет канонического лейбла);
    # отдаём значение как есть (как AttendeeViewSet.retrieve). Резолюция кода → лейбл =
    # follow-up (нужен справочник типов документов).
    doc_type = serializers.CharField(source="docTypeId")
    created_at = serializers.DateTimeField(source="dateAdd", allow_null=True)

    class Meta(ReviewQueueSerializer.Meta):
        fields = ReviewQueueSerializer.Meta.fields + [
            "photo",
            "doc_scan",
            "birth_date",
            "is_resident",
            "country",
            "post",
            "transcription",
            "doc_type",
            "created_at",
        ]

    def get_photo(self, obj):
        return self._media_url(obj.photo)

    def get_doc_scan(self, obj):
        return self._media_url(obj.docScan)

    def _media_url(self, file_field):
        # Пустой ImageField → None (не битый `<img>`); `.url` бросает ValueError без
        # файла — защитно. С request-контекстом — абсолютный URL (protected /media/
        # под session-cookie); без контекста (фикстура) — относительный (детерминирован).
        if not file_field:
            return None
        try:
            url = file_field.url
        except ValueError:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request is not None else url
