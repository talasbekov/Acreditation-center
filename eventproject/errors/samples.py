"""Story fe-1.1 — РЕАЛЬНЫЕ DRF error-ответы (генерируются live handler-ом).

Единый источник для:
  • фикстуры `frontend/src/errors/__fixtures__/drf-error-samples.json` (round-trip
    zod-теста на фронте);
  • backend анти-дрейф теста (`test_error_contract.py`): регенерация == закоммичено.
Покрывает оба пути handler-а: `CodedValidationError` (с params) и fallback (ErrorDetail.code).
"""

from rest_framework.exceptions import ErrorDetail, PermissionDenied, ValidationError

from eventproject.api.exceptions import rfc7807_exception_handler
from eventproject.errors import coded_error

_CTX = {"view": None, "args": (), "kwargs": {}, "request": None}


def _sample_exceptions():
    return [
        coded_error("iin_dob_mismatch", field="iin", iin_dob="05.12.1985", entered_dob="12.05.1985"),
        coded_error("iin_checksum", field="iin"),
        coded_error("duplicate_attendee", field="iin"),
        coded_error("events_not_found", field="event_ids", missing=[7, 9]),
        ValidationError({"photo": [ErrorDetail("Файл слишком большой (максимум 5 МБ)", code="photo_too_large")]}),
        ValidationError({"title": [ErrorDetail("This field is required.", code="required")]}),
        PermissionDenied(),
    ]


def build_samples():
    """Список реальных response.data из `rfc7807_exception_handler` по репрезентативным ошибкам."""
    return [dict(rfc7807_exception_handler(exc, _CTX).data) for exc in _sample_exceptions()]
