"""P2: страницы RU/KZ/EN обслуживает один набор обработчиков; язык — из URL.

Тесты закрепляют поведение, которое раньше было только в русской копии и
расходилось в казахской и английской.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import resolve
from django.utils import timezone

from eventproject import page_lang
from eventproject.models import Attendee, Event, Operator, OperatorAccessEvent, Request
from eventproject.views import add_attendee, send, show_request, user_login

PREFIXES = {"ru": "", "kz": "/kz", "en": "/en"}


class Fixture(TestCase):
    def setUp(self):
        today = date.today()
        self.event = Event.objects.create(name_rus="Форум", name_kaz="Форум", name_eng="Forum", title="E",
                                          date_start=today, date_end=today + timedelta(days=5))
        self.user = User.objects.create_user("op", password="Strong-Pass-123", first_name="Оп")
        self.operator = Operator.objects.create(user=self.user, role="operator", patronymic="О", phone_number="+7")
        self.operator.events.add(self.event)

    def _request(self, attendees=1):
        req = Request.objects.create(name="R-77", event=self.event, status="Active", created_by=self.operator,
                                     registration_time=timezone.now())
        for i in range(attendees):
            Attendee.objects.create(surname=f"Ф{i}", firstname="И", post="P", countryId="1000000840", is_resident=False,
                                    docTypeId="1", docSeries="", docNumber=f"N{i}", docIssue="X", sexId="1",
                                    visitObjects="Z", transcription="T", request=req, dateAdd=timezone.now())
        return req


class OneHandlerPerPageTests(TestCase):
    def test_language_urls_resolve_to_the_same_view(self):
        for path, view in (("show/1/", show_request), ("add_attendee/1/", add_attendee), ("send/1/", send),
                           ("user_login/", user_login)):
            for lang, prefix in PREFIXES.items():
                with self.subTest(path=path, lang=lang):
                    match = resolve(f"{prefix}/{path}")
                    self.assertIs(match.func, view)
                    self.assertEqual(match.kwargs.get("lang", "ru"), lang)

    def test_every_text_has_three_languages(self):
        for key, values in page_lang._TEXT.items():
            self.assertEqual(set(values), set(page_lang.LANGS), key)
            self.assertTrue(all(values.values()), key)


class LanguageSpecificBehaviourTests(Fixture):
    def test_anonymous_user_goes_to_login_of_same_language(self):
        req = self._request()
        for lang, prefix in PREFIXES.items():
            with self.subTest(lang=lang):
                for url in (f"{prefix}/application/", f"{prefix}/show/{req.pk}/"):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response["Location"].startswith(f"{prefix}/user_login/?next="), response["Location"])
                # Раньше /kz/send/ без входа уводил на русскую страницу входа.
                response = self.client.post(f"{prefix}/send/{req.pk}/")
                self.assertTrue(response["Location"].startswith(f"{prefix}/user_login/"), response["Location"])

    def test_login_records_access_event_and_honours_next(self):
        for lang, prefix in PREFIXES.items():
            with self.subTest(lang=lang):
                client = Client()
                response = client.post(f"{prefix}/user_login/", {"username": "op", "password": "Strong-Pass-123"})
                self.assertRedirects(response, f"{prefix}/application/", fetch_redirect_response=False)
                response = Client().post(f"{prefix}/user_login/", {"username": "op", "password": "Strong-Pass-123",
                                                                   "next": f"{prefix}/show/1/"})
                self.assertEqual(response["Location"], f"{prefix}/show/1/")
        self.assertEqual(OperatorAccessEvent.objects.filter(operator=self.operator, event_type="login").count(), 6)

    def test_login_form_carries_next_in_every_language(self):
        for prefix in PREFIXES.values():
            with self.subTest(prefix=prefix):
                page = self.client.get(f"{prefix}/user_login/?next={prefix}/show/5/").content.decode()
                self.assertIn(f'<input type="hidden" name="next" value="{prefix}/show/5/">', page)

    def test_wrong_and_deactivated_login_messages(self):
        inactive = User.objects.create_user("gone", password="Strong-Pass-123", is_active=False)
        Operator.objects.create(user=inactive, patronymic="Г", phone_number="+7")
        for lang, prefix in PREFIXES.items():
            with self.subTest(lang=lang):
                page = self.client.post(f"{prefix}/user_login/", {"username": "op", "password": "bad"}).content.decode()
                self.assertIn(page_lang.text("login_bad", lang), page)
                page = self.client.post(f"{prefix}/user_login/", {"username": "gone", "password": "Strong-Pass-123"}).content.decode()
                self.assertIn(page_lang.text("account_disabled", lang), page)

    @override_settings(AXES_FAILURE_LIMIT=2)
    def test_lockout_message_is_localized(self):
        for lang, prefix in PREFIXES.items():
            with self.subTest(lang=lang):
                from axes.utils import reset
                reset()
                client = Client()
                for _ in range(2):
                    client.post(f"{prefix}/user_login/", {"username": "op", "password": "WRONG"})
                response = client.post(f"{prefix}/user_login/", {"username": "op", "password": "Strong-Pass-123"})
                self.assertEqual(response.status_code, 429)
                self.assertIn(page_lang.text("login_locked", lang), response.content.decode())

    def test_password_change_keeps_session_and_clears_force_flag(self):
        for lang, prefix in PREFIXES.items():
            with self.subTest(lang=lang):
                self.operator.force_password_change = True
                self.operator.save()
                old = f"Old-Pass-{lang}"
                self.user.set_password(old)
                self.user.save()
                client = Client()
                client.force_login(self.user)
                new = f"New-Pass-{lang}"
                page = client.post(f"{prefix}/change_password/", {"old_password": old, "new_password": new,
                                                                  "new_password_repeat": new}).content.decode()
                self.assertIn(page_lang.text("pw_changed", lang), page)
                # Раньше KZ/EN разлогинивали пользователя после смены пароля.
                self.assertEqual(client.get(f"{prefix}/application/").status_code, 200)
                self.operator.refresh_from_db()
                self.assertFalse(self.operator.force_password_change)

    def test_deleting_last_attendee_deletes_request_in_every_language(self):
        self.client.force_login(self.user)
        for lang, prefix in PREFIXES.items():
            with self.subTest(lang=lang):
                req = self._request(attendees=1)
                only = Attendee.objects.get(request=req)
                response = self.client.post(f"{prefix}/delete_attendee/", {"attendee_id": only.pk})
                self.assertEqual(response.status_code, 200)
                page = response.content.decode()
                self.assertIn(page_lang.text("request_deleted", lang, name="R-77"), page)
                self.assertNotIn("None", page)
                self.assertNotIn("/add_attendee/None", page)
                self.assertFalse(Request.objects.filter(pk=req.pk).exists())

    def test_add_attendee_without_csrf_field_is_refused_everywhere(self):
        req = self._request()
        self.client.force_login(self.user)
        for prefix in PREFIXES.values():
            with self.subTest(prefix=prefix):
                self.assertEqual(self.client.post(f"{prefix}/add_attendee/{req.pk}/", {"last_name": "X"}).status_code, 403)

    def test_rejections_have_the_same_prefix_in_every_language(self):
        req = self._request()
        self.client.force_login(self.user)
        data = {"csrfmiddlewaretoken": "x", "last_name": "Б", "first_name": "Т", "latin_name": "B T", "dob": "2099-01-01",
                "sex": "1", "citizenship": "1000000840", "post": "P", "document_type": "1", "doc_number": "Q1",
                "doc_date_start": "2020-01-01", "doc_date_end": "2034-01-01", "doc_issuer": "X", "visit_objects": "Z"}
        for lang, prefix in PREFIXES.items():
            with self.subTest(lang=lang):
                page = self.client.post(f"{prefix}/add_attendee/{req.pk}/", data).content.decode()
                expected = page_lang.text("add_failed", lang, reason=page_lang.text("dob_future", lang))
                self.assertIn(expected, page)
                # Введённые данные сохраняются в форме на всех языках.
                self.assertIn('value="B T"', page)
