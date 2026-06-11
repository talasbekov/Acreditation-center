import logging

from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse

logger = logging.getLogger("eventproject")


def health_check(request):
    try:
        connections["default"].ensure_connection()
    except OperationalError:
        logger.critical(
            "DB connectivity check failed",
            extra={
                "user_id": None,
                "role": "system",
                "action": "health.check",
                "obj_type": "db",
                "obj_id": None,
                "ip": request.META.get("REMOTE_ADDR"),
            },
        )
        return JsonResponse(
            {"status": "error", "db": "unreachable"},
            status=503,
        )

    return JsonResponse({"status": "ok", "db": "ok"})
