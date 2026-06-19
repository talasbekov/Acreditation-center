from django.conf import settings


class RoleBasedSessionTimeoutMiddleware:
    """
    Устанавливает SESSION_COOKIE_AGE на основе роли пользователя.
    Вызывается ПОСЛЕ get_response, чтобы захватить состояние после login().
    Супероператор/Админ (is_superuser=True): 4 ч (14400 сек).
    Оператор: 12 ч (43200 сек).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Вызываем set_expiry ПОСЛЕ view, чтобы корректно захватить
        # состояние после login() на первом запросе.
        if request.user.is_authenticated:
            if request.user.is_superuser:
                request.session.set_expiry(14400)   # 4 ч
            else:
                request.session.set_expiry(43200)   # 12 ч
        return response
