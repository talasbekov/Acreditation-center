"""Общие хелперы legacy function-based вью (RU/KZ/EN)."""

from django.core.exceptions import PermissionDenied

from eventproject.models import Operator


def require_operator(user):
    """Возвращает `Operator` пользователя либо отдаёт 403.

    BE-18: аутентифицированный пользователь без строки `Operator` не должен ронять
    legacy-вью 500-кой на `Operator.objects.get`. `PermissionDenied` рендерится Django
    как 403. Безопасно и внутри `try/except` (Exception-ветка перехватит как и раньше).
    """
    try:
        return Operator.objects.get(user=user)
    except Operator.DoesNotExist:
        raise PermissionDenied("Требуется профиль оператора")
