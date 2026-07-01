"""Story fe-1.5 — трёхъязычные имена событий (serving + rendering).

⭐ Поля `name_rus`/`name_kaz`/`name_eng` УЖЕ существуют (0001_initial) — это НЕ модель/миграция.
Покрытие:
  • AC1 — поля существуют; `Event.clean()` требует полное имя у КОНТЕЙНЕРА, НЕ у листа.
  • AC2 (Q1) — `EventSerializer` отдаёт `name_ru/kz/en` (source=), пустые как есть (null).
  • AC4 (Q3) — `ReviewQueueSerializer.sub_event_names` {ru,kz,en} аддитивно; `sub_event_name`
    (frozen fe-3.1) = ru/legacy fallback, НЕ изменился.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from eventproject.models import Event
from eventproject.serializers.event import EventSerializer
from eventproject.serializers.review_queue import ReviewQueueSerializer
from eventproject.tests.test_attendee_api import (
    VALID_IIN,
    _make_attendee,
    _make_operator,
    _make_request,
)


class TrilingualFieldsTests(TestCase):
    def test_event_has_trilingual_name_fields(self):
        # AC1: поля СУЩЕСТВУЮТ (верифицируем, не добавляем — реш.#1).
        names = {f.name for f in Event._meta.get_fields()}
        self.assertTrue({"name_rus", "name_kaz", "name_eng"} <= names)

    def test_container_requires_full_trilingual_name(self):
        # AC1: контейнер без kz/en → ValidationError (clean(), госотчётность).
        container = Event(name_rus="Рус", name_kaz="", name_eng="", is_container=True, title="C")
        with self.assertRaises(ValidationError):
            container.clean()

    def test_leaf_without_kz_en_is_valid(self):
        # AC1: лист (не контейнер) без kz/en — валиден (fallback покрывает на рендере, реш.#4).
        Event(name_rus="Только рус", is_container=False, title="L").clean()  # не бросает


class EventSerializerTrilingualTests(TestCase):
    def test_serializer_exposes_name_ru_kz_en(self):
        # AC2 (Q1): API-поля name_ru/kz/en через source= на name_rus/kaz/eng.
        ev = Event.objects.create(name_rus="Пресс-центр", name_kaz="Баспасөз", name_eng="Press", title="T")
        data = EventSerializer(ev).data
        self.assertEqual(data["name_ru"], "Пресс-центр")
        self.assertEqual(data["name_kz"], "Баспасөз")
        self.assertEqual(data["name_en"], "Press")

    def test_serializer_empty_names_as_stored(self):
        # AC3: сервер НЕ подменяет — пустые kz/en отдаются как есть (null); фронт делает fallback.
        ev = Event.objects.create(name_rus="Только рус", title="T2")  # name_kaz/eng = null
        data = EventSerializer(ev).data
        self.assertEqual(data["name_ru"], "Только рус")
        self.assertIsNone(data["name_kz"])
        self.assertIsNone(data["name_en"])


class ReviewQueueSubEventNamesTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(name_rus="Пресс", name_kaz="Баспасөз", name_eng="Press", title="T")
        self.op_user, self.op = _make_operator("op", "operator", event=self.event)
        self.req = _make_request(self.event, self.op)
        self.att = _make_attendee(self.req, status="submitted", iin=VALID_IIN)

    def test_sub_event_names_triplet(self):
        # AC4 (Q3): nested {ru,kz,en}.
        data = ReviewQueueSerializer(self.att).data
        self.assertEqual(data["sub_event_names"], {"ru": "Пресс", "kz": "Баспасөз", "en": "Press"})

    def test_sub_event_name_frozen_ru_fallback_unchanged(self):
        # AC4: sub_event_name (frozen fe-3.1) НЕ изменился — ru/legacy fallback.
        self.assertEqual(ReviewQueueSerializer(self.att).data["sub_event_name"], "Пресс")

    def test_sub_event_names_empty_kz_en_as_stored(self):
        # AC3: лист с только name_rus → триплет kz/en null (фронт fallback на ru).
        ev2 = Event.objects.create(name_rus="Только рус", title="T2")
        op2_user, op2 = _make_operator("op2", "operator", event=ev2)
        att2 = _make_attendee(_make_request(ev2, op2), status="submitted", iin=VALID_IIN)
        data = ReviewQueueSerializer(att2).data
        self.assertEqual(data["sub_event_names"], {"ru": "Только рус", "kz": None, "en": None})
