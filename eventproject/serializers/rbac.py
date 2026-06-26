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


def get_operator_attendee_queryset(user):
    """Story hd-5.3: ЕДИНЫЙ scope-резолвер УЧАСТНИКОВ — `events ∩ category` (AND).

    Переиспользует `get_operator_events(user)` для событийной части (fail-closed,
    БЕЗ upward-traversal — привязка к листу ≠ доступ к siblings/родителю). При
    заданном `Operator.category` дополнительно сужает по категории (AND-семантика).
    `superuser`/`superoperator` — полный доступ (aggregate), без category-сужения.

    Единственный источник scope участников (attendee_api и пр.) — не дублировать
    `request__event__in=...` по вьюсетам (расхождение с E3a fe-3-1). Attendee-специфичен
    (фильтры по `request__event`/`category_id`); для других моделей — `get_operator_events`.
    """
    from eventproject.models import Attendee  # ленивый импорт (избежать цикла)

    events = get_operator_events(user)
    qs = Attendee.objects.filter(request__event__in=events)

    # AND-семантика: только для роли operator с заданной category.
    if getattr(user, "role", None) not in ("superuser", "superoperator"):
        try:
            category_id = user.operator.category_id
        except (AttributeError, Operator.DoesNotExist):
            category_id = None
        if category_id is not None:
            qs = qs.filter(category_id=category_id)

    return qs
