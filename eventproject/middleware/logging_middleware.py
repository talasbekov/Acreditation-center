import logging

logger = logging.getLogger("request_logger")


class RequestLoggingMiddleware:
    # AC-1 taxonomy: WARNING — подозрительная активность. На HTTP-уровне это
    # auth/authz/abuse-сигналы: 401 (доступ без аутентификации), 403 (отказ
    # авторизации/CSRF/RBAC), 429 (превышение лимита запросов — перебор/
    # злоупотребление). Прочие 4xx (400/404) остаются INFO: одиночные клиентские
    # ошибки сами по себе не подозрительны и зашумили бы WARNING.
    SUSPICIOUS_STATUSES = frozenset({401, 403, 429})

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        level, action = self._classify(response.status_code)
        self._log_request(
            request,
            status=response.status_code,
            level=level,
            action=action,
        )
        return response

    def _classify(self, status):
        if status in self.SUSPICIOUS_STATUSES:
            return logging.WARNING, "request.suspicious"
        return logging.INFO, "request.completed"

    def process_exception(self, request, exception):
        self._log_request(request, 500, logging.ERROR, "request.failed")

    def _log_request(self, request, status, level, action):
        # Route templates exclude request values, including activation credentials.
        # Кто (id и роль) нужен, чтобы разобрать WARNING 401/403/429. Имя пользователя,
        # IP и значения из адреса не пишутся (этап B, test_legacy_privacy): IP значимых
        # действий хранит audit_log, неудачных входов — django-axes.
        match = getattr(request, "resolver_match", None)
        user = getattr(request, "user", None)
        is_auth = bool(user is not None and user.is_authenticated)
        logger.log(level, action, extra={
            "user_id": user.id if is_auth else None,
            "role": getattr(user, "role", None) if is_auth else None,
            "action": action, "obj_type": "http.request",
            "method": request.method, "path": match.route if match else "<unmatched>",
            "status": status,
        })
