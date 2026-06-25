"""Story 3.3 — тесты конечного автомата статусов участника (AC-5)."""

from itertools import product

from django.test import SimpleTestCase

from eventproject.state_machine import (
    ATTENDEE_STATUSES,
    AttendeeStatus,
    InvalidStatusTransition,
    assert_transition,
    can_transition,
)

S = AttendeeStatus

VALID_TRANSITIONS = [
    (S.DRAFT, S.SUBMITTED),
    (S.SUBMITTED, S.IN_REVIEW),
    (S.IN_REVIEW, S.READY),
    (S.IN_REVIEW, S.SUBMITTED),   # возврат на доработку (5-й переход)
    (S.READY, S.EXPORTED),
]

INVALID_TRANSITIONS = [
    (S.DRAFT, S.EXPORTED),
    (S.DRAFT, S.READY),
    (S.SUBMITTED, S.EXPORTED),
    (S.READY, S.DRAFT),
    (S.EXPORTED, S.READY),        # терминальный
    (S.IN_REVIEW, S.DRAFT),
]


class ValidTransitionTests(SimpleTestCase):
    def test_all_five_valid_transitions_allowed(self):
        self.assertEqual(len(VALID_TRANSITIONS), 5)
        for current, target in VALID_TRANSITIONS:
            self.assertTrue(
                can_transition(current, target),
                f"{current}→{target} должен быть разрешён",
            )
            # assert_transition не бросает
            assert_transition(current, target)


class InvalidTransitionTests(SimpleTestCase):
    def test_invalid_transitions_rejected(self):
        self.assertGreaterEqual(len(INVALID_TRANSITIONS), 3)
        for current, target in INVALID_TRANSITIONS:
            self.assertFalse(
                can_transition(current, target),
                f"{current}→{target} должен быть запрещён",
            )
            with self.assertRaises(InvalidStatusTransition):
                assert_transition(current, target)

    def test_exported_is_terminal(self):
        for target in (S.DRAFT, S.SUBMITTED, S.IN_REVIEW, S.READY):
            self.assertFalse(can_transition(S.EXPORTED, target))

    def test_only_defined_edges_allowed(self):
        # Исчерпывающе: разрешены РОВНО 5 рёбер из VALID_TRANSITIONS, остальное — нет.
        allowed = set(VALID_TRANSITIONS)
        for current, target in product(ATTENDEE_STATUSES, ATTENDEE_STATUSES):
            expected = (current, target) in allowed
            self.assertEqual(
                can_transition(current, target),
                expected,
                f"{current}→{target}: ожидалось allowed={expected}",
            )

    def test_self_transition_forbidden(self):
        for s in ATTENDEE_STATUSES:
            self.assertFalse(can_transition(s, s), f"self-переход {s}→{s} запрещён")

    def test_unknown_status_rejected(self):
        self.assertFalse(can_transition("bogus", S.SUBMITTED))
        self.assertFalse(can_transition(S.DRAFT, "bogus"))
        with self.assertRaises(InvalidStatusTransition):
            assert_transition("bogus", "also-bogus")


class ModelDefaultTests(SimpleTestCase):
    def test_attendee_status_defaults_to_draft(self):
        # Дефолт поля модели = draft (без обращения к БД).
        from eventproject.models import Attendee

        field = Attendee._meta.get_field("status")
        self.assertEqual(field.default, S.DRAFT)
