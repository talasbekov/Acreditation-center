from django.contrib.auth import SESSION_KEY, logout

from eventproject.services.session_revocation import SESSION_GENERATION_KEY, active_generation


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
        if SESSION_KEY in request.session:
            user = request.user
            current = active_generation(user.pk) if user.is_authenticated else None
            # Sessions created before this feature default to generation zero.
            if current is None or request.session.get(SESSION_GENERATION_KEY, 0) != current:
                logout(request)

        response = self.get_response(request)
        # Вызываем set_expiry ПОСЛЕ view, чтобы корректно захватить
        # состояние после login() на первом запросе.
        if request.user.is_authenticated:
            if request.user.is_superuser:
                request.session.set_expiry(14400)   # 4 ч
            else:
                request.session.set_expiry(43200)   # 12 ч
        return response
