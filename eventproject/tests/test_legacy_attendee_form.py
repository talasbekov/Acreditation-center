"""Story 3.5 — legacy Django UI: серверная ИИН/residency-валидация формы.

Проверяет, что legacy add_attendee (RU/KZ/EN) и RU update_attendee вызывают
единый `validators/residency.resolve_residency` (→ validators/iin.validate_iin):
- некорректный ИИН резидента РК блокирует сохранение с понятным сообщением,
  введённые данные не теряются (AC-2);
- несовпадение ИИН↔дата рождения даёт дословное сообщение (FR23/AC-2);
- нерезидент без ИИН сохраняется (iin=NULL, is_resident=False), без KeyError (AC-1);
- валидный резидент сохраняется со статусом draft (AC happy path).

Все три локализованные копии add_attendee должны вести себя одинаково — иначе
KZ/EN-интерфейс остаётся каналом обхода валидации (NFR8).
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone

from eventproject.models import Attendee, Event, Operator, Request

# Валидный ИИН для даты рождения 1990-01-01 (корректная контрольная цифра 7).
VALID_IIN = "900101300007"
# 12 цифр, неверная контрольная цифра.
INVALID_IIN = "123456789012"
KZ = "1000000105"
NON_KZ = "1000000840"

# Три локализованные копии формы добавления (один и тот же URL-name).
ADD_ENDPOINTS = [
    "/add_attendee/{rid}/",
    "/kz/add_attendee/{rid}/",
    "/en/add_attendee/{rid}/",
]


class LegacyAttendeeFormValidationTest(TestCase):
    def setUp(self):
        cache.clear()  # сброс django-ratelimit (RATELIMIT_ENABLE=True в тестах)
        self.client = Client()
        self.user = User.objects.create_user(username="op", password="password123")
        self.operator = Operator.objects.create(
            user=self.user,
            patronymic="Test",
            phone_number="+70000000000",
            workplace="Test Workplace",
        )
        self.event = Event.objects.create(
            name_rus="Test Event",
            name_kaz="Test Event",
            name_eng="Test Event",
            event_code="T1",
            date_start=date.today(),
            date_end=date.today(),
            city_code="AK",
        )
        self.req = Request.objects.create(
            name="Test Request",
            event=self.event,
            status="Active",
            created_by=self.operator,
            registration_time=timezone.now(),
        )
        self.client.force_login(self.user)

    def _upload(self, name="f.jpg"):
        return SimpleUploadedFile(name, b"x" * 2048, content_type="image/jpeg")

    def _payload(self, **overrides):
        data = {
            "req_id": self.req.id,
            "csrfmiddlewaretoken": "known-token",
            "last_name": "Тестовский",
            "first_name": "Иван",
            "patronymic": "Петрович",
            "latin_name": "Ivan Testovskiy",
            "iin": VALID_IIN,
            "dob": "1990-01-01",
            "sex": "M",
            "citizenship": KZ,
            "post": "Инженер",
            "document_type": "passport",
            "doc_series": "AA",
            "doc_number": "123456",
            "doc_date_start": "2020-01-01",
            "doc_date_end": "2030-01-01",
            "doc_issuer": "МВД",
            "visit_objects": "Объект",
            "category": "CAT",
            "photo": self._upload("photo.jpg"),
            "doc_photo": self._upload("doc.jpg"),
        }
        data.update(overrides)
        return data

    def _create_attendee(self, **overrides):
        defaults = dict(
            surname="Тестовский",
            firstname="Иван",
            patronymic="Петрович",
            transcription="Ivan Testovskiy",
            iin=VALID_IIN,
            birthDate=date(1990, 1, 1),
            post="Инженер",
            countryId=KZ,
            docTypeId="passport",
            docSeries="AA",
            docNumber="123456",
            docBegin=date(2020, 1, 1),
            docEnd=date(2030, 1, 1),
            docIssue="МВД",
            photo=self._upload("photo.jpg"),
            docScan=self._upload("doc.jpg"),
            sexId="M",
            dateAdd=timezone.now(),
            visitObjects="Объект",
            request=self.req,
            dateEnd=date.today(),
            stickId="CAT",
        )
        defaults.update(overrides)
        return Attendee.objects.create(**defaults)

    def _post(self, endpoint, **overrides):
        return self.client.post(
            endpoint.format(rid=self.req.id),
            self._payload(**overrides),
            REMOTE_ADDR="127.0.0.1",
        )

    # ── AC-2: некорректный ИИН блокирует сохранение + данные сохранены ──
    def test_invalid_iin_blocks_save_and_preserves_data(self):
        for endpoint in ADD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                Attendee.objects.all().delete()
                cache.clear()
                response = self._post(endpoint, iin=INVALID_IIN)
                self.assertEqual(Attendee.objects.count(), 0)
                self.assertContains(response, "контрольная цифра")
                # AC-2: введённые данные сохранены — не нужно перепечатывать.
                self.assertContains(response, "Тестовский")

    # ── AC-1: нерезидент без ИИН сохраняется (iin=NULL), без KeyError ──
    def test_non_resident_without_iin_saved(self):
        for endpoint in ADD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                Attendee.objects.all().delete()
                cache.clear()
                payload = self._payload(citizenship=NON_KZ)
                payload.pop("iin")  # форма нерезидента не передаёт ИИН
                response = self.client.post(
                    endpoint.format(rid=self.req.id),
                    payload,
                    REMOTE_ADDR="127.0.0.1",
                )
                self.assertEqual(response.status_code, 200)
                attendee = Attendee.objects.get(surname="Тестовский")
                self.assertIsNone(attendee.iin)
                self.assertFalse(attendee.is_resident)

    # ── happy path: валидный резидент сохраняется со статусом draft ──
    def test_valid_resident_saved(self):
        for endpoint in ADD_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                Attendee.objects.all().delete()
                cache.clear()
                response = self._post(endpoint)
                self.assertEqual(response.status_code, 200)
                attendee = Attendee.objects.get(surname="Тестовский")
                self.assertEqual(attendee.iin, VALID_IIN)
                self.assertTrue(attendee.is_resident)
                self.assertEqual(attendee.status, "draft")

    # ── FR23/AC-2: несовпадение ИИН↔дата рождения — дословное сообщение ──
    def test_iin_birthdate_mismatch_message(self):
        # VALID_IIN кодирует 01.01.1990; введём другую дату рождения.
        response = self._post(ADD_ENDPOINTS[0], dob="1985-05-12")
        self.assertEqual(Attendee.objects.count(), 0)
        self.assertContains(response, "не совпадает")

    # ── update (RU): некорректный ИИН не перезаписывает запись ──
    def test_update_invalid_iin_blocks_save(self):
        attendee = self._create_attendee(iin=VALID_IIN)
        response = self.client.post(
            "/update_attendee/%d/" % attendee.id,
            self._payload(iin=INVALID_IIN),
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertContains(response, "контрольная цифра")
        attendee.refresh_from_db()
        self.assertEqual(attendee.iin, VALID_IIN)  # запись не перезаписана

    # ── update (RU): при ошибке валидации введённые даты не теряются (AC-2) ──
    def test_update_invalid_iin_preserves_typed_dates(self):
        attendee = self._create_attendee(iin=VALID_IIN)
        response = self.client.post(
            "/update_attendee/%d/" % attendee.id,
            self._payload(iin=INVALID_IIN, dob="1992-03-15"),
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertContains(response, "контрольная цифра")
        # До фикса date-поля рендерились |date по POST-строке → пусто.
        self.assertContains(response, 'value="1992-03-15"')  # введённая дата рождения
        self.assertContains(response, 'value="2020-01-01"')  # дата выдачи документа
