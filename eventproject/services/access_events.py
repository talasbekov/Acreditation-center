"""Story 2.4 — запись событий истории доступа оператора.

Тонкий helper поверх модели `OperatorAccessEvent`, чтобы точки записи
(create / login / change_password / deactivate / reactivate) не дублировали
логику. Audit-JSON (`audit_log`) пишется отдельно в местах вызова.
"""

from eventproject.models import OperatorAccessEvent


def record_access_event(operator, event_type, *, actor=None, ip="", details=None):
    """Создаёт запись истории доступа.

    operator   — экземпляр Operator.
    event_type — одно из OperatorAccessEvent.EVENT_TYPE_CHOICES.
    actor      — User, совершивший действие (для login/password — сам оператор).
    ip         — REMOTE_ADDR.
    details    — опциональный dict с дополнительным контекстом.
    """
    return OperatorAccessEvent.objects.create(
        operator=operator,
        event_type=event_type,
        actor=actor,
        ip=ip or "",
        details=details or {},
    )
