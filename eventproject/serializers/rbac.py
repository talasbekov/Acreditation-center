def get_operator_events(user):
    """Возвращает queryset Event для данного пользователя согласно роли."""
    if user.role in ("superuser", "superoperator"):
        from eventproject.models import Event
        return Event.objects.all()
    try:
        return user.operator.events.all()
    except Exception:
        from eventproject.models import Event
        return Event.objects.none()
