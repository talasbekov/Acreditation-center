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
    try:
        return user.operator.events.all()
    except Operator.DoesNotExist:
        return Event.objects.none()
    except Exception:
        # Неожиданная ошибка (DB/operational) — fail-closed, но НЕ маскируем молча.
        logger.exception(
            "get_operator_events failed for user_id=%s", getattr(user, "id", None)
        )
        return Event.objects.none()
