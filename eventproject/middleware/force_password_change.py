"""Story 2.3 (AC-5) — принудительная смена пароля при первом входе.

Оператор, созданный через авто-генерацию credentials, имеет
`force_password_change=True`. Пока флаг не снят (т.е. пароль не сменён):
- HTML-запросы перенаправляются на страницу смены пароля (302);
- API-запросы (`/api/`) получают 403 JSON (не могут следовать HTML-редиректу).

Флаг снимается во вьюхе `change_password` после успешной смены пароля.
"""

import logging

from django.http import JsonResponse
from django.shortcuts import redirect

logger = logging.getLogger("eventproject")

# Путь смены пароля захардкожен (не reverse): в urls.py есть несколько URL с
# именем "change_password" (default/kz/en), и reverse() резолвит в последний.
CHANGE_PASSWORD_PATH = "/change_password/"

# Сегменты пути (ТОЧНОЕ совпадение сегмента), которые не редиректим. Якорим по
# сегментам, а не по подстроке: иначе путь вроде /events/change_password_report/
# обошёл бы форс-смену (review finding).
_EXEMPT_SEGMENTS = {"change_password", "new_password", "logout"}
_EXEMPT_PREFIXES = ("/static", "/media", "/api/health")


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_force_change(request):
            if request.path.startswith("/api/"):
                return JsonResponse(
                    {
                        "detail": "Требуется смена пароля.",
                        "code": "password_change_required",
                    },
                    status=403,
                )
            return redirect(CHANGE_PASSWORD_PATH)
        return self.get_response(request)

    def _should_force_change(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or user.is_superuser:
            return False

        operator = getattr(user, "operator", None)
        if operator is None or not getattr(operator, "force_password_change", False):
            return False

        path = request.path
        if path.startswith(_EXEMPT_PREFIXES):
            return False
        segments = {seg for seg in path.split("/") if seg}
        if segments & _EXEMPT_SEGMENTS:
            return False
        return True
