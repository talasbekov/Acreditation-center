import logging

from eventproject.models import Event, Operator

logger = logging.getLogger("eventproject")


def get_operator_events(user):
    """Возвращает queryset Event для пользователя согласно роли.

    Fail-closed: неаутентифицированный / без роли / без Operator → пустой queryset.
    """
    # AnonymousUser не имеет monkey-patched .role — deny by default (без 500).
    if not getattr(user, "is_authenticated", False):
        return Event.objects.none()
    if getattr(user, "role", None) in ("superuser", "superoperator"):
        return Event.objects.all()
    if user.role != "operator":
        return Event.objects.none()
    try:
        return user.operator.events.all()
    except Operator.DoesNotExist:
        return Event.objects.none()
    except Exception:
        # Неожиданная ошибка (DB/operational) — fail-closed, но НЕ маскируем молча.
        logger.error("get_operator_events failed")
        return Event.objects.none()
