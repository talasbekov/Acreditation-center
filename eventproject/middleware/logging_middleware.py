import logging

logger = logging.getLogger("request_logger")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._log_request(request, response.status_code, logging.INFO, "request.completed")
        return response

    def process_exception(self, request, exception):
        self._log_request(request, 500, logging.ERROR, "request.failed")

    def _log_request(self, request, status, level, action):
        # Route templates exclude request values, including activation credentials.
        match = getattr(request, "resolver_match", None)
        logger.log(level, action, extra={
            "action": action, "obj_type": "http.request",
            "method": request.method, "path": match.route if match else "<unmatched>",
            "status": status,
        })
