"""Story 3.4 — DRF serializer участника.

Валидация ИИН/резидентства делегируется единым источникам:
`validators/residency.resolve_residency` (→ `validators/iin.validate_iin`).
Дубли в рамках мероприятия — `services/intake.find_duplicate` (этап C).
"""

from datetime import date
import re

from django.http import QueryDict
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from eventproject.errors import coded_error
from eventproject.models import Attendee, Request
from eventproject.serializers.rbac import get_operator_events
from eventproject.services import intake
from eventproject.validators.iin import mask_iin
from eventproject.validators.photo import (
    check_upload_size,
    convert_pdf_to_jpeg,
    is_pdf,
    validate_image_file,
)

# Файловые поля: пустая строка в multipart → трактуем как «без файла».
_FILE_FIELDS = ("photo", "docScan")
from eventproject.validators.residency import is_known_country, resolve_residency


def raise_if_duplicate(event_id, attrs, instance=None):
    """400 с полем ``iin`` или ``docNumber``, если участник уже есть в мероприятии."""

    def current(field):
        if field in attrs:
            return attrs[field]
        return getattr(instance, field, None)

    code = intake.find_duplicate(
        event_id,
        country_id=current("countryId"),
        iin=current("iin"),
        doc_type=current("docTypeId"),
        doc_series=current("docSeries"),
        doc_number=current("docNumber"),
        exclude_pk=instance.pk if instance is not None else None,
    )
    if code:
        field = "iin" if code == "iin" else "docNumber"
        # Код ошибки (duplicate_attendee / duplicate_document) переживает агрегацию
        # сериализатора через ErrorDetail.code — SPA переводит его по коду.
        error_code = "duplicate_attendee" if code == "iin" else "duplicate_document"
        raise serializers.ValidationError(
            {field: serializers.ErrorDetail(intake.duplicate_text(code, "ru"), code=error_code)}
        )


_RU_ERRORS = {
    "required": "Обязательное поле.",
    "blank": "Обязательное поле.",
    "null": "Обязательное поле.",
    "invalid": "Неверное значение.",
    "max_length": "Слишком длинное значение (не больше {max_length} символов).",
    "does_not_exist": "Значение не найдено.",
    "incorrect_type": "Неверное значение.",
    "datetime": "Нужна дата, а не дата и время.",
}


def _check_dates(attrs):
    """Документ уже выдан и ещё действует, дата рождения не в будущем (как в HTML-форме)."""
    today = date.today()
    errors = {}
    if attrs.get("docBegin") and attrs["docBegin"] > today:
        errors["docBegin"] = "Дата выдачи документа еще не наступила"
    if attrs.get("docEnd") and attrs["docEnd"] < today:
        errors["docEnd"] = "Истек срок документа"
    if attrs.get("birthDate") and attrs["birthDate"] > today:
        errors["birthDate"] = "Проверьте дату рождения"
    if errors:
        raise serializers.ValidationError(errors)


def _strip_blank_file_fields(data, blank_fields):
    """Вернуть ``data`` без указанных пустых файловых полей.

    P1-6: для QueryDict сохраняем multi-value (``getlist``) и html-input маркер — НЕ
    схлопываем в плоский dict (иначе multi-value поля усекаются до последнего значения,
    а DRF теряет html-input-обработку пустых/списочных полей). Используем `setlist`
    (без deepcopy file-handle'ов, в отличие от ``QueryDict.copy()``).
    """
    blank_fields = set(blank_fields)
    if hasattr(data, "lists"):
        cleaned = QueryDict(mutable=True)
        for key, values in data.lists():
            if key in blank_fields:
                continue
            cleaned.setlist(key, values)
        return cleaned
    return {key: value for key, value in data.items() if key not in blank_fields}


# Story fe-3.7 (review P2): скраб 12-значного ИИН в admin-authored причине возврата (`review_comment`)
# перед выдачей оператору/админам. Причина — свободный текст проверяющего, мог содержать
# сырой ИИН → на masked-safe list-поверхности (+ cross-tenant видимость у superuser/
# superoperator) это утечка. Зеркало защитного `audit._scrub_pii`.
_IIN_RE = re.compile(r"\b\d{12}\b")


def _scrub_reason(text):
    if not text:
        return text
    return _IIN_RE.sub(lambda m: mask_iin(m.group()), text)


class AttendeeSerializer(serializers.ModelSerializer):
    # PK-поля и iin объявлены явно (iin — EncryptedCharField, не полагаемся на
    # авто-маппинг DRF).
    request = serializers.PrimaryKeyRelatedField(queryset=Request.objects.all())
    iin = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=12
    )
    # Story 5.3: photo/docScan — FileField (не ImageField), чтобы docScan мог
    # принять PDF и пройти конвертацию ДО валидации изображения. Все проверки —
    # в validate_photo/validate_docScan (единый validators/photo.py).
    photo = serializers.FileField(required=False, allow_null=True)
    docScan = serializers.FileField(required=False, allow_null=True)
    # fe-3.7 (review P2): причина возврата со скрабом ИИН (admin free-text → баннер edit).
    # SerializerMethodField — только чтение: меняется лишь через return/.
    review_comment = serializers.SerializerMethodField()

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
            "photo",
            "docScan",
            "sexId",
            "visitObjects",
            "transcription",
            "stickId",
            "request",
            "category",
            "dateEnd",
            "is_resident",
            "status",
            "dateAdd",
            # Причина возврата (со скрабом ИИН) и счётчик возвратов.
            "review_comment",
            "return_count",
        ]
        # Выставляются сервером/логикой, не клиентом. review_comment — причина
        # возврата (меняется только через return/); SerializerMethodField, поэтому
        # не в read_only_fields.
        read_only_fields = [
            "id", "is_resident", "status", "dateAdd", "return_count",
        ]
        # Этап D: как в HTML-форме — серия документа и «Кем выдан» необязательны,
        # категория участника (stickId) необязательна (у резидента РК не хранится).
        extra_kwargs = {
            "docSeries": {"required": False, "allow_blank": True, "default": ""},
            "docIssue": {"required": False, "allow_blank": True, "default": ""},
            "stickId": {"required": False, "allow_blank": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Этап D: сообщения о пустых и неверных значениях — по-русски (SPA показывает их
        # под полями; LANGUAGE_CODE проекта en-us, поэтому стандартные тексты DRF английские).
        for field in self.fields.values():
            field.error_messages.update(_RU_ERRORS)

    def to_internal_value(self, data):
        # Пустая строка для файлового поля (multipart `photo=''`) → «без файла».
        # DRF FileField иначе падает с английским «not a file» без field-маппинга.
        # _strip_blank_file_fields сохраняет multi-value QueryDict (P1-6) и не
        # deepcopy'ит file-handle'ы (QueryDict.copy() их ломает).
        blanks = [f for f in _FILE_FIELDS if data.get(f) == ""]
        if blanks:
            data = _strip_blank_file_fields(data, blanks)
        return super().to_internal_value(data)

    def validate_photo(self, value):
        # Story 5.3 AC-3: размер/вертикальность/разрешение фото участника.
        if value in (None, ""):
            return value
        validate_image_file(value)
        return value

    def validate_docScan(self, value):
        # Story 5.3 AC-4: PDF → JPEG (первая страница), далее та же валидация,
        # что и у фото (AC-3) — решение Erda 2026-06-24.
        if value in (None, ""):
            return value
        if is_pdf(value):
            # AC-3: лимит 5 МБ — на ИСХОДНЫЙ PDF, ДО конвертации (иначе мерялся бы
            # на сконвертированном JPEG).
            check_upload_size(value)
            value = convert_pdf_to_jpeg(value)
        validate_image_file(value)
        return value

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        def current(field):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, None)

        req = current("request")

        # RBAC (Story 3.4 review 2026-06-23): участник может принадлежать ТОЛЬКО
        # мероприятию оператора. Проверяем ДО любых event-scoped запросов — иначе
        # дедуп-запрос ниже утечёт факт существования ИИН в чужом мероприятии
        # (400 раньше 403). Эта же проверка закрывает RBAC-bypass на update:
        # `request` writable, поэтому без неё участника можно переназначить на
        # Request чужого события. Единый источник RBAC для create и update.
        request_obj = self.context.get("request")
        if request_obj is not None and req is not None:
            if not get_operator_events(request_obj.user).filter(
                id=req.event_id
            ).exists():
                raise PermissionDenied("Нет доступа к этому мероприятию.")

        country_id = current("countryId")
        iin = current("iin")
        birth_date = current("birthDate")

        # BE-5: непустой, но неизвестный countryId (напр. малформ «1000000105aaaa»)
        # нельзя молча трактовать как нерезидента — иначе ИИН резидента отбрасывается
        # без сигнала. Сверяем со справочником Country.country_code. Пустой/None
        # countryId пропускаем (нет выбора страны → текущее поведение нерезидента).
        if str(country_id or "").strip() and not is_known_country(country_id):
            raise coded_error("country_unknown", field="countryId")

        # Residency + ИИН (Story 3.1/3.2): обязательность/валидность/нормализация.
        result = resolve_residency(country_id, iin, birth_date)
        if result.error:
            # fe-1.1: машинный код + динамические params (iin_dob_mismatch) → handler.
            raise coded_error(
                result.code or "iin_format", field="iin", **(result.params or {})
            )
        attrs["is_resident"] = result.is_resident
        attrs["iin"] = result.iin  # None для нерезидента

        # P1-4 / этап D: у резидента РК категория скрыта формой и не хранится.
        if result.is_resident and "stickId" in attrs:
            attrs["stickId"] = ""

        # Этап D: при добавлении — те же проверки дат, что у HTML-формы (views/attendee.py).
        if instance is None:
            _check_dates(attrs)

        # Этап C: единое правило дублей (ИИН резидента / документ нерезидента).
        # Под блокировкой мероприятия проверка повторяется в AttendeeViewSet.
        if req is not None:
            raise_if_duplicate(req.event_id, attrs, instance)
        return attrs

    def get_review_comment(self, obj):
        return _scrub_reason(obj.review_comment)


class AttendeeListSerializer(serializers.ModelSerializer):
    """Story 5.5 — лёгкий сериализатор СПИСКА.

    Только колонки списка + **маскированный** ИИН (`mask_iin` — последние 4,
    решение Erda 2026-06-24). Полный ИИН в списке НЕ отдаётся (PII-минимизация);
    detail/create/update используют полный `AttendeeSerializer`.
    """

    iin_masked = serializers.SerializerMethodField()
    # Этап C: черновик, возвращённый проверяющим. Саму причину список не отдаёт.
    returned = serializers.SerializerMethodField()
    # Этап D: контекст строки реестра — номер заявки и мероприятие (без доп. запросов:
    # queryset подтягивает request__event через select_related).
    request_name = serializers.CharField(source="request.name", read_only=True)
    event_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendee
        fields = [
            "id",
            "surname",
            "firstname",
            "patronymic",
            "status",
            "category",
            "dateAdd",
            "iin_masked",
            "returned",
            "request_name",
            "event_name",
            # fe-3.7: сколько раз заявку возвращали (причина — только в карточке).
            "return_count",
        ]

    def get_event_name(self, obj):
        event = obj.request.event
        return event.name_rus or event.title or ""

    def get_iin_masked(self, obj):
        return mask_iin(obj.iin)

    def get_returned(self, obj):
        return obj.status == "draft" and bool(obj.review_comment)
