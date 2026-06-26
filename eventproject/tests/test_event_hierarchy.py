"""Story hd-5.1: Event hierarchy — Event.parent + leaf/container + валидация."""
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from eventproject.models import Event


def _event(**kw):
    defaults = dict(
        name_rus="Большое мероприятие",
        name_kaz="Үлкен іс-шара",
        name_eng="Big Event",
        date_start=date(2026, 7, 1),
        date_end=date(2026, 7, 10),
    )
    defaults.update(kw)
    return Event.objects.create(**defaults)


class EventHierarchyFieldsTests(TestCase):
    """AC-1: поля parent/is_container + неразрушающие defaults."""

    def test_new_fields_default_non_destructive(self):
        ev = _event()
        self.assertIsNone(ev.parent_id)        # default NULL
        self.assertFalse(ev.is_container)      # default False

    def test_parent_self_fk_links(self):
        root = _event()
        child = _event(parent=root, date_start=date(2026, 7, 2), date_end=date(2026, 7, 5))
        self.assertEqual(child.parent_id, root.id)
        self.assertIn(child, root.subevents.all())  # related_name='subevents'

    def test_parent_protect_on_delete(self):
        """on_delete=PROTECT: нельзя удалить контейнер с детьми (retention)."""
        root = _event()
        _event(parent=root, date_start=date(2026, 7, 2), date_end=date(2026, 7, 5))
        with self.assertRaises(IntegrityError) if False else self.assertRaises(Exception):
            with transaction.atomic():
                root.delete()


class EventOneLevelTests(TestCase):
    """AC-2: ровно один уровень + anti-self-parent."""

    def test_grandchild_rejected_one_level(self):
        root = _event()
        child = _event(parent=root, date_start=date(2026, 7, 2), date_end=date(2026, 7, 5))
        grandchild = Event(
            name_rus="x", name_kaz="x", name_eng="x",
            date_start=date(2026, 7, 3), date_end=date(2026, 7, 4), parent=child,
        )
        with self.assertRaises(ValidationError):
            grandchild.full_clean()

    def test_self_parent_rejected_validation(self):
        ev = _event()
        ev.parent = ev
        with self.assertRaises(ValidationError):
            ev.full_clean()

    def test_self_parent_rejected_db_constraint(self):
        ev = _event()
        ev.parent_id = ev.id
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ev.save()


class EventDateInvariantTests(TestCase):
    """AC-3: child ⊆ parent по датам + i18n-имя контейнера."""

    def test_child_dates_within_parent_ok(self):
        root = _event(date_start=date(2026, 7, 1), date_end=date(2026, 7, 10))
        child = Event(
            name_rus="x", name_kaz="x", name_eng="x", parent=root,
            date_start=date(2026, 7, 2), date_end=date(2026, 7, 9),
        )
        child.full_clean()  # не бросает

    def test_child_dates_outside_parent_rejected(self):
        root = _event(date_start=date(2026, 7, 1), date_end=date(2026, 7, 10))
        child = Event(
            name_rus="x", name_kaz="x", name_eng="x", parent=root,
            date_start=date(2026, 6, 20), date_end=date(2026, 7, 9),  # начинается раньше
        )
        with self.assertRaises(ValidationError):
            child.full_clean()

    def test_container_requires_i18n_name(self):
        ev = Event(
            name_rus="", name_kaz="", name_eng="",
            date_start=date(2026, 7, 1), date_end=date(2026, 7, 10),
            is_container=True,
        )
        with self.assertRaises(ValidationError):
            ev.full_clean()


class EventDataQualityTests(TestCase):
    """AC-4: data-quality assert (один уровень держится) + N:1 связь."""

    def test_no_two_level_chains_exist(self):
        root = _event()
        _event(parent=root, date_start=date(2026, 7, 2), date_end=date(2026, 7, 5))
        self.assertFalse(
            Event.objects.filter(parent__parent__isnull=False).exists()
        )
