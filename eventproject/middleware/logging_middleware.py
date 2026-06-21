import logging

from django.utils.timezone import now

logger = logging.getLogger("request_logger")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._log_request(
            request,
            status=response.status_code,
            level=logging.INFO,
            action="request.completed",
        )
        return response

    def process_exception(self, request, exception):
        # Django вызывает этот хук, когда view бросает необработанное исключение.
        # Логируем как ERROR (AC-1: ERROR — исключения), чтобы упавшие запросы —
        # самые важные для наблюдаемости — не терялись. Возвращаем None, чтобы
        # обычная обработка исключения Django продолжилась.
        self._log_request(
            request,
            status=500,
            level=logging.ERROR,
            action="request.failed",
            error=exception.__class__.__name__,
        )
        return None

    def _log_request(self, request, status, level, action, error=None):
        is_auth = request.user.is_authenticated
        user = request.user if is_auth else "Anonymous"
        # M4: логируем паттерн маршрута (resolver_match.route), а не request.path —
        # в самом пути могут быть PII-сегменты (username, request_id). Query-string
        # также исключена (в параметрах может быть PII: ИИН, № документа).
        match = getattr(request, "resolver_match", None)
        path = match.route if match is not None else request.path

        extra = {
            "user_id": getattr(request.user, "id", None) if is_auth else None,
            "role": getattr(request.user, "role", None) if is_auth else None,
            "action": action,
            "obj_type": "http.request",
            "obj_id": None,
            "ip": self.get_client_ip(request),
            "method": request.method,
            "path": path,
            "status": status,
            "request_user": str(user),
            "request_time": now().isoformat(),
        }
        if error is not None:
            extra["error"] = error

        logger.log(level, action, extra=extra)

    def get_client_ip(self, request):
        # M3: используем REMOTE_ADDR — так же, как django-axes и audit_log.
        # X-Forwarded-For задаётся клиентом и не санируется на уровне приложения,
        # поэтому доверять первому значению из заголовка нельзя (спуфинг IP,
        # рассинхрон с аудитом). Если перед приложением стоит доверенный прокси —
        # разбирайте XFF централизованно (django-ipware с настроенными доверенными
        # прокси), а не первым значением заголовка.
        return request.META.get("REMOTE_ADDR")
