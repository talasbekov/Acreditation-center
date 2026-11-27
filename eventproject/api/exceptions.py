from rest_framework.views import exception_handler


def _flatten_detail(value):
    if isinstance(value, (list, tuple)):
        return "; ".join(_flatten_detail(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_flatten_detail(item)}" for key, item in value.items())
    return str(value)


def rfc7807_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    field = None

    if isinstance(detail, dict):
        for key in detail:
            if key not in {"non_field_errors", "detail"}:
                field = key
                break

    if isinstance(detail, dict) and "detail" in detail:
        detail_str = _flatten_detail(detail["detail"])
    else:
        detail_str = _flatten_detail(detail)

    data = {
        "type": f"https://httpstatuses.com/{response.status_code}",
        "title": response.status_text,
        "detail": detail_str,
        "field": field,
    }
    # Этап D: ошибки по каждому полю (`field` и `detail` остаются для прежних клиентов) —
    # SPA-форма показывает их под своими полями, без префикса «post: …».
    if field is not None:
        data["errors"] = {
            key: _flatten_detail(value)
            for key, value in detail.items()
            if key not in {"non_field_errors", "detail"}
        }
    response.data = data
    return response
