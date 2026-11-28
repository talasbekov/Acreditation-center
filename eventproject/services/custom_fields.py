"""Дополнительные поля мероприятия: проверка значений участника.

Значения хранятся в `Attendee.custom_field_values` как {"<id поля>": "строка"}.
Проверка общая для формы оператора, саморегистрации и внешнего API.
"""

from datetime import date

from eventproject.errors import CodedValidationError
from eventproject.models import CustomField

FIELD = "custom_field_values"


def _fail(code, field):
    raise CodedValidationError(code, field=FIELD, params={"name": field.field_name})


def _clean_one(field, raw):
    value = "" if raw is None else str(raw).strip()
    if value == "":
        return ""
    if field.field_type == "number":
        try:
            float(value.replace(",", "."))
        except ValueError:
            _fail("custom_field_invalid", field)
    elif field.field_type == "date":
        try:
            date.fromisoformat(value)
        except ValueError:
            _fail("custom_field_invalid", field)
    elif field.field_type == "select":
        if value not in [str(o) for o in (field.options or [])]:
            _fail("custom_field_invalid", field)
    if len(value) > 1000:
        _fail("custom_field_invalid", field)
    return value


def clean_values(event_id, raw, existing=None):
    """Проверить и нормализовать значения доп. полей участника.

    raw — то, что прислал клиент (dict или None); existing — сохранённые значения
    (при правке). Неизвестные ключи отбрасываются; обязательное поле не может быть
    пустым. Возвращает новый dict для сохранения.
    """
    if raw is not None and not isinstance(raw, dict):
        raise CodedValidationError("invalid", field=FIELD)
    merged = dict(existing or {})
    merged.update({str(k): v for k, v in (raw or {}).items()})
    cleaned = {}
    for field in CustomField.objects.filter(event_id=event_id):
        value = _clean_one(field, merged.get(str(field.id)))
        if field.is_required and value == "":
            _fail("custom_field_required", field)
        if value != "":
            cleaned[str(field.id)] = value
    return cleaned


def field_payload(field):
    return {
        "id": field.id,
        "field_name": field.field_name,
        "field_type": field.field_type,
        "is_required": field.is_required,
        "options": field.options or [],
        "sort_order": field.sort_order,
    }
