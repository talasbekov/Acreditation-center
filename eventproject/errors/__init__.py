"""Story fe-1.1 — пакет машинного контракта ошибок.

`CodedValidationError` — машинно-кодированная ошибка валидации с `params`. Сознательно
НЕ подкласс DRF `ValidationError`: `Serializer.is_valid()` переагрегирует `ValidationError`
(`as_serializer_error` → `get_error_detail`), теряя произвольные `params`. `APIException`
(status 400) пробрасывается из `validate()`/`validate_<field>()` НЕТРОНУТЫМ, донося
`code` + `params` + `field` до `rfc7807_exception_handler`.

Для ошибок БЕЗ динамических `params` достаточно `serializers.ValidationError(msg, code="...")`
— код переживает агрегацию через `ErrorDetail.code` (handler его извлекает). `CodedValidationError`
нужен там, где `params` динамические (напр. `iin_dob_mismatch`).
"""

from rest_framework import status
from rest_framework.exceptions import APIException

from .registry import ERROR_CODES, all_codes, code_exists, spec_for

__all__ = [
    "CodedValidationError",
    "CodedConflict",
    "coded_error",
    "conflict_error",
    "ERROR_CODES",
    "all_codes",
    "code_exists",
    "spec_for",
]


class CodedValidationError(APIException):
    """Ошибка валидации с машинным кодом и динамическими params (status 400)."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code, field=None, params=None):
        spec = spec_for(code)
        self.code = code if code in ERROR_CODES else "unknown"
        self.field = field if field is not None else spec.get("field")
        self.params = dict(params or {})
        template = spec.get("detail", "")
        try:
            self.detail_default = template.format(**self.params) if self.params else template
        except (KeyError, IndexError, ValueError):
            # ValueError — битый format-spec; не давать .format() уронить запрос (500).
            self.detail_default = template
        # APIException.__init__ кладёт detail (дефолтный язык — только логи/не-UI).
        super().__init__(self.detail_default or self.code)


def coded_error(code, field=None, **params):
    """Удобный конструктор: ``raise coded_error("iin_dob_mismatch", field="iin", iin_dob=..., entered_dob=...)``."""
    return CodedValidationError(code, field=field, params=params)


class CodedConflict(CodedValidationError):
    """Конфликт состояния (status 409) с ТЕМ ЖЕ машинным конвертом ``{type, params, field}``.

    Story fe-3.4: approve/return не-«На проверке» заявки = конфликт состояния (нельзя
    сделать двойной/нелегальный FSM-переход), а не ошибка валидации ввода. `coded_error`
    всегда даёт 400 (`CodedValidationError.status_code`) — для 409 нужен отдельный путь.

    Подкласс `CodedValidationError` СОЗНАТЕЛЬНО: `rfc7807_exception_handler` ловит ошибку
    `isinstance(exc, CodedValidationError)`-веткой (Path 1) и отдаёт `status=exc.status_code`.
    Переопределённый class-level `status_code` → 409 без правок handler'а / FE-маппера.
    """

    status_code = status.HTTP_409_CONFLICT


def conflict_error(code, field=None, **params):
    """409-конструктор: ``raise conflict_error("status_transition_invalid", field="status")``."""
    return CodedConflict(code, field=field, params=params)
