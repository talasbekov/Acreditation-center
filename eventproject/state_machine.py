"""Attendee state machine (Story 3.3) — единый источник правды переходов статуса.

Чистый модуль (только stdlib), чтобы models.py мог импортировать без цикла.
Применение переходов (audit_log, проверки при submit, edit-lock после ready,
RBAC) — Story 3.4 (AttendeeViewSet); ready→exported — Epic 4. Здесь — статусы,
карта разрешённых переходов и примитивы can_transition/assert_transition.
"""


class AttendeeStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    READY = "ready"
    EXPORTED = "exported"


ATTENDEE_STATUSES = (
    AttendeeStatus.DRAFT,
    AttendeeStatus.SUBMITTED,
    AttendeeStatus.IN_REVIEW,
    AttendeeStatus.READY,
    AttendeeStatus.EXPORTED,
)

ATTENDEE_STATUS_CHOICES = [(s, s) for s in ATTENDEE_STATUSES]

# Разрешённые переходы конечного автомата (FR24).
# frozenset — неизменяемые значения: исключаем случайную порчу карты (в т.ч.
# терминальности exported) сторонним кодом.
ALLOWED_TRANSITIONS = {
    AttendeeStatus.DRAFT: frozenset({AttendeeStatus.SUBMITTED}),
    AttendeeStatus.SUBMITTED: frozenset({AttendeeStatus.IN_REVIEW}),
    # in_review: одобрить (ready) либо вернуть на доработку (submitted).
    AttendeeStatus.IN_REVIEW: frozenset({AttendeeStatus.READY, AttendeeStatus.SUBMITTED}),
    AttendeeStatus.READY: frozenset({AttendeeStatus.EXPORTED}),
    AttendeeStatus.EXPORTED: frozenset(),  # терминальный
}


class InvalidStatusTransition(Exception):
    """Недопустимый переход статуса участника."""


def can_transition(current, target) -> bool:
    """True, если переход current → target разрешён. False для неизвестных статусов."""
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def assert_transition(current, target) -> None:
    """Бросает InvalidStatusTransition, если переход недопустим (вкл. неизвестные статусы)."""
    if not can_transition(current, target):
        raise InvalidStatusTransition(
            f"Недопустимый переход статуса: {current!r} → {target!r}"
        )
