import logging

from django.db import connections
from django.http import JsonResponse

logger = logging.getLogger("eventproject")


def health_check(request):
    try:
        connections["default"].ensure_connection()
    except Exception as exc:
        # Health check: ЛЮБОЙ сбой соединения с БД означает «нездоров». Ловим широко,
        # т.к. недоступность БД может прийти не только как OperationalError, но и как
        # InterfaceError (битый сокет) или иное (AC-3: всегда 503 + CRITICAL).
        logger.critical(
            "DB connectivity check failed",
            extra={
                "user_id": None,
                "role": "system",
                "action": "health.check",
                "obj_type": "db",
                "obj_id": None,
                "ip": request.META.get("REMOTE_ADDR") or "unknown",
                "method": request.method,
                "path": request.path,
                "status": 503,
                "error": exc.__class__.__name__,
            },
        )
        return JsonResponse(
            {"status": "error", "db": "unreachable"},
            status=503,
        )

    return JsonResponse({"status": "ok", "db": "ok"})
