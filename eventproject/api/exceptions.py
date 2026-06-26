"""Story fe-1.1 — RFC 7807 + машинный код в `type` (ревизия R1, architecture.md:784-793).

Shape: ``{"type": "<snake_case_code>", "field": "<name|null>", "params": {...},
"detail": "<дефолтный язык|null>"}``. `detail` — ТОЛЬКО для логов/не-UI потребителей
(downstream, SIEM); НЕ источник UI-текста (его рендерит React-маппер из errors.json).

Два пути:
  • ``CodedValidationError`` (errors/__init__.py) — пробрасывается из validate()
    нетронутым → берём code/params/field напрямую (несёт динамические params).
  • любой иной DRF-exception — делегируем в default-handler, затем извлекаем `field`
    и машинный `code` из ``ErrorDetail.code`` (переживает агрегацию сериализатора).
    Непомеченный/неизвестный код → ``unknown`` + WARNING-лог.
"""

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler

from eventproject.errors import CodedValidationError
from eventproject.errors.registry import ERROR_CODES

logger = logging.getLogger("eventproject")


def _flatten_detail(value):
    if isinstance(value, (list, tuple)):
        return "; ".join(_flatten_detail(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_flatten_detail(item)}" for key, item in value.items())
    return str(value)


def _first_field(detail):
    """Имя проблемного поля — первый ключ dict, кроме служебных."""
    if isinstance(detail, dict):
        for key in detail:
            if key not in {"non_field_errors", "detail"}:
                return key
    return None


def _code_in_subtree(detail):
    """Первый ``ErrorDetail.code`` в ПОДДЕРЕВЕ (любой код, не только реестровый)."""
    if isinstance(detail, dict):
        for value in detail.values():
            code = _code_in_subtree(value)
            if code:
                return code
    elif isinstance(detail, (list, tuple)):
        for item in detail:
            code = _code_in_subtree(item)
            if code:
                return code
    else:
        return getattr(detail, "code", None)
    return None


def _field_and_code(detail):
    """field + code из ОДНОГО поддерева (не глобально) — иначе type мог бы прийти
    с другого поля, чем field (мульти-field ошибка). Код вне реестра → unknown
    (чтобы у каждого эмитнутого type был ключ в errors.json)."""
    field = _first_field(detail)
    if field is not None and isinstance(detail, dict):
        raw_code = _code_in_subtree(detail[field])
    else:
        raw_code = _code_in_subtree(detail)
    code = raw_code if raw_code in ERROR_CODES else None
    return field, code


def rfc7807_exception_handler(exc, context):
    # Путь 1 — машинно-кодированная ошибка с params (пробрасывается из validate() нетронутой).
    if isinstance(exc, CodedValidationError):
        return Response(
            {
                "type": exc.code,
                "field": exc.field,
                "params": exc.params,
                "detail": exc.detail_default,
            },
            status=exc.status_code,
        )

    # Путь 2 — любой иной DRF-exception: делегируем и извлекаем код из ErrorDetail.code.
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    field, code = _field_and_code(detail)
    if code is None:
        code = "unknown"
        logger.warning(
            "rfc7807: непомеченная ошибка → type=unknown",
            extra={"action": "error.unmapped", "obj_type": exc.__class__.__name__},
        )

    if isinstance(detail, dict) and "detail" in detail:
        detail_str = _flatten_detail(detail["detail"])
    else:
        detail_str = _flatten_detail(detail)

    response.data = {
        "type": code,
        "field": field,
        "params": {},
        "detail": detail_str,
    }
    return response
