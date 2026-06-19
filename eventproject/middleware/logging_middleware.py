import logging
from django.utils.timezone import now

logger = logging.getLogger("request_logger")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = request.user if request.user.is_authenticated else "Anonymous"
        ip = self.get_client_ip(request)
        method = request.method
        # M4: только path без query-string — в параметрах может быть PII (IIN, № документа).
        path = request.path
        status = response.status_code

        logger.info(
            "request.completed",
            extra={
                "user_id": getattr(request.user, "id", None)
                if request.user.is_authenticated
                else None,
                "role": getattr(request.user, "role", None)
                if request.user.is_authenticated
                else None,
                "action": "request.completed",
                "obj_type": "http.request",
                "obj_id": None,
                "ip": ip,
                "method": method,
                "path": path,
                "status": status,
                "request_user": str(user),
                "request_time": now().isoformat(),
            },
        )

        return response

    def get_client_ip(self, request):
        # M3: используем REMOTE_ADDR — так же, как django-axes и audit_log.
        # X-Forwarded-For задаётся клиентом и не санируется на уровне приложения,
        # поэтому доверять первому значению из заголовка нельзя (спуфинг IP,
        # рассинхрон с аудитом). Если перед приложением стоит доверенный прокси —
        # разбирайте XFF централизованно (django-ipware с настроенными доверенными
        # прокси), а не первым значением заголовка.
        return request.META.get("REMOTE_ADDR")
