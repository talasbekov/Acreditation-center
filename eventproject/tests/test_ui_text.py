"""P2: общие шаблоны RU/KZ/EN — строки интерфейса из словаря `eventproject/ui_text.py`."""

import re
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import TestCase
from django.utils import timezone

from directories.models import Category as DirCategory, City, Country, DocumentType, Sex
from eventproject.models import Attendee, Event, Operator, Request
from eventproject.ui_text import UI

TEMPLATES = Path(settings.BASE_DIR) / "templates"
T_TAG = re.compile(r"""{%\s*t\s+(["'])(.+?)\1""")
CYRILLIC = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]")


def visible_text(html):
    """Текст страницы без скриптов, стилей, тегов и атрибутов."""
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


class CatalogTests(TestCase):
    def test_every_template_string_has_kz_and_en(self):
        keys = set()
        for path in TEMPLATES.rglob("*.html"):
            keys.update(m.group(2) for m in T_TAG.finditer(path.read_text(encoding="utf-8")))
        self.assertGreater(len(keys), 60)
        missing = sorted(k for k in keys if not (UI.get(k, {}).get("kz") and UI.get(k, {}).get("en")))
        self.assertEqual(missing, [])

    def test_placeholders_survive_translation(self):
        for key, values in UI.items():
            names = set(re.findall(r"{(\w+)}", key))
            for lang, value in values.items():
                self.assertEqual(set(re.findall(r"{(\w+)}", value)), names, (key, lang))

    def test_iin_errors_have_three_languages_and_match_validator(self):
        from eventproject import page_lang
        from eventproject.validators.residency import resolve_residency

        kz = "1000000105"
        cases = [("", date(1990, 1, 1)), ("12345", date(1990, 1, 1)), ("123456789012", date(1990, 1, 1)),
                 ("900101300007", date(1985, 5, 12)), ("901301300007", None)]  # 13-й месяц
        codes = set()
        for iin, dob in cases:
            result = resolve_residency(kz, iin, dob)
            with self.subTest(iin=iin):
                self.assertTrue(result.code, result)
                codes.add(result.code)
                self.assertEqual(page_lang.residency_error(result, "ru"), result.error)
                self.assertEqual(page_lang.text(result.code, "ru", **(result.params or {})), result.error)
                for lang in ("kz", "en"):
                    self.assertNotEqual(page_lang.residency_error(result, lang), result.error)
        self.assertEqual(codes, {"iin_required", "iin_format", "iin_checksum", "iin_dob_mismatch", "iin_date_invalid"})

    def test_tag_escapes_substitutions(self):
        out = Template('{% load ui_tags %}{% t "Добро пожаловать, {name}" name=n %}').render(
            Context({"lang": "en", "n": "<b>x</b>"}))
        self.assertEqual(out, "Welcome, &lt;b&gt;x&lt;/b&gt;")


class Fixture(TestCase):
    def setUp(self):
        today = date.today()
        Country.objects.create(country_code="1000000105", name_rus="Казахстан", name_kaz="Қазақстан", name_eng="Kazakhstan", country_iso="KZ")
        Country.objects.create(country_code="1000000840", name_rus="США", name_kaz="АҚШ", name_eng="USA", country_iso="US")
        Sex.objects.create(sex_code="1", name_rus="Мужской", name_kaz="Ер", name_eng="Male")
        for code, ru, kz, en in (("1000000002", "Паспорт иностранца", "Шетел паспорты", "Foreign passport"),
                                 ("1000000004", "Вид на жительство", "Ықтиярхат", "Residence permit")):
            DocumentType.objects.create(doc_code=code, name_rus=ru, name_kaz=kz, name_eng=en)
        DirCategory.objects.create(category_code="7", index="7", name_rus="Пресса", name_kaz="Баспасөз", name_eng="Press")
        DirCategory.objects.create(category_code="8", index="8", name_rus="Гость", name_kaz="Қонақ", name_eng="Guest")
        City.objects.create(city_code="1", index="1", name_rus="Астана", name_kaz="Астана", name_eng="Astana")
        self.event = Event.objects.create(name_rus="Форум", name_kaz="Форумы", name_eng="Forum", title="F", city_code="1",
                                          date_start=today, date_end=today + timedelta(days=5))
        self.user = User.objects.create_user("op", password="x", first_name="John", last_name="Smith")
        self.operator = Operator.objects.create(user=self.user, role="operator", patronymic="P", phone_number="+7")
        self.operator.events.add(self.event)
        self.req = Request.objects.create(name="R1", event=self.event, status="Active", created_by=self.operator,
                                          registration_time=timezone.now())
        self.attendee = Attendee.objects.create(
            surname="Brown", firstname="Tom", post="Engineer", countryId="1000000840", is_resident=False,
            docTypeId="1000000004", docSeries="AB", docNumber="N1", docIssue="State", sexId="1",
            visitObjects="Hall", transcription="BROWN TOM", request=self.req, dateAdd=timezone.now(), stickId="8",
            birthDate=date(1990, 1, 1), docBegin=date(2020, 1, 1), docEnd=date(2034, 1, 1),
        )
        self.client.force_login(self.user)

    def pages(self, prefix):
        return [f"{prefix}/application/", f"{prefix}/show/{self.req.pk}/", f"{prefix}/preview/{self.req.pk}/",
                f"{prefix}/add_attendee/{self.req.pk}/", f"{prefix}/update_attendee/{self.attendee.pk}/",
                f"{prefix}/change_password/"]


class SharedTemplatesTests(Fixture):
    def test_english_pages_have_no_russian_interface_text(self):
        for url in self.pages("/en"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                leftovers = [w for w in visible_text(response.content.decode()).split() if CYRILLIC.search(w)]
                self.assertEqual(leftovers, [])
        self.client.logout()
        page = visible_text(self.client.get("/en/user_login/").content.decode())
        self.assertFalse(CYRILLIC.search(page), page)

    def test_kazakh_pages_use_kazakh_strings(self):
        expected = {
            "/kz/application/": ["Сізге қолжетімді шаралардың тізімі", "Форумы", "John Smith, қош келдіңіз!"],
            f"/kz/show/{self.req.pk}/": ["Форумы шарасына берілген өтініш(R1), тізімде 1 қатысушы бар", "Азаматтығы:", "АҚШ", "Ықтиярхат", "Қонақ"],
            f"/kz/add_attendee/{self.req.pk}/": ["«Форумы» шарасына қатысушы қосу", "Тегі", "Қатысушы қосу"],
            f"/kz/update_attendee/{self.attendee.pk}/": ["Өзгерістерді сақтау", "Әкесінің аты", "«Форумы» шарасының қатысушысын өзгерту"],
        }
        for url, words in expected.items():
            with self.subTest(url=url):
                page = self.client.get(url).content.decode()
                for word in words:
                    self.assertIn(word, page)

    def test_links_and_forms_stay_in_the_same_language(self):
        for prefix in ("", "/kz", "/en"):
            with self.subTest(prefix=prefix):
                page = self.client.get(f"{prefix}/show/{self.req.pk}/").content.decode()
                for path in (f"/add_attendee/{self.req.pk}/", f"/preview/{self.req.pk}/", "/delete_attendee/",
                             f"/update_attendee/{self.attendee.pk}/", "/logout/", "/change_password/"):
                    self.assertIn(f'"{prefix}{path}"', page)
                form = self.client.get(f"{prefix}/add_attendee/{self.req.pk}/").content.decode()
                self.assertIn(f'action="{prefix}/add_attendee/{self.req.pk}/"', form)
                self.assertRegex(form, r'<input class="form-check-input" type="checkbox"[^>]*id="consent" required>')
                self.assertIn('id="category_group"', form)

    def test_language_switch_marks_current_language(self):
        for lang, prefix in (("RU", ""), ("KZ", "/kz"), ("EN", "/en")):
            page = self.client.get(f"{prefix}/application/").content.decode()
            self.assertIn(f"<b>{lang}</b>", page)
            self.assertEqual(page.count("<b>KZ</b>") + page.count("<b>RU</b>") + page.count("<b>EN</b>"), 1)

    def test_edit_form_preselects_document_type_and_category(self):
        page = self.client.get(f"/kz/update_attendee/{self.attendee.pk}/").content.decode()
        self.assertRegex(page, r'value="1000000004"\s+selected')
        self.assertRegex(page, r'value="8"\s+selected')

    def test_edit_in_kazakh_returns_to_kazakh_request(self):
        data = {"csrfmiddlewaretoken": "x", "last_name": "Brown", "first_name": "Tim", "patronymic": "", "latin_name": "BROWN TIM",
                "dob": "1990-01-01", "sex": "1", "citizenship": "1000000840", "post": "Engineer", "document_type": "1000000004",
                "doc_series": "AB", "doc_number": "N1", "doc_date_start": "2020-01-01", "doc_date_end": "2034-01-01",
                "doc_issuer": "State", "visit_objects": "Hall"}
        response = self.client.post(f"/kz/update_attendee/{self.attendee.pk}/", data)
        self.assertRedirects(response, f"/kz/show/{self.req.pk}/", fetch_redirect_response=False)
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.firstname, "Tim")


class OperatorReferencePagesTests(Fixture):
    """Этап D: страницы оператора на утверждённом эталоне (отчёт 20)."""

    def test_pages_use_reference_styles(self):
        for prefix in ("", "/kz", "/en"):
            for url in self.pages(prefix):
                with self.subTest(url=url):
                    page = self.client.get(url).content.decode()
                    self.assertIn("/static/css/ds.css", page)
                    self.assertNotIn("<style", page)
                    self.assertNotIn("button--color-blue", page)
                    self.assertNotIn("jquery", page.lower())
                    self.assertIn('href="#content"', page)

    def test_language_switch_keeps_the_page(self):
        page = self.client.get(f"/kz/show/{self.req.pk}/").content.decode()
        self.assertIn(f'href="/show/{self.req.pk}/" lang="ru"', page)
        self.assertIn(f'href="/en/show/{self.req.pk}/" lang="en"', page)
        self.assertIn(f'href="/kz/show/{self.req.pk}/" lang="kk" aria-current="true"', page)

    def test_every_form_field_has_a_label(self):
        for prefix in ("", "/kz", "/en"):
            for url in (f"{prefix}/add_attendee/{self.req.pk}/", f"{prefix}/update_attendee/{self.attendee.pk}/",
                        f"{prefix}/change_password/"):
                with self.subTest(url=url):
                    page = self.client.get(url).content.decode()
                    fields = re.findall(r'<(?:input|select|textarea)\b(?![^>]*type="hidden")[^>]*>', page)
                    self.assertTrue(fields)
                    labels = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', page))
                    for field in fields:
                        field_id = re.search(r'\bid="([^"]+)"', field)
                        self.assertIsNotNone(field_id, field)
                        self.assertIn(field_id.group(1), labels, field)

    def test_add_form_keeps_typed_values_after_error(self):
        data = {"csrfmiddlewaretoken": "x", "last_name": "Брауни", "first_name": "Том", "latin_name": "BROWNIE TOM",
                "dob": "1990-01-01", "sex": "1", "citizenship": "1000000840", "category": "8", "post": "Инженер",
                "document_type": "1000000004", "doc_series": "", "doc_number": "N9", "doc_date_start": "2999-01-01",
                "doc_date_end": "2034-01-01", "doc_issuer": "", "visit_objects": "Зал"}
        page = self.client.post(f"/add_attendee/{self.req.pk}/", data).content.decode()
        self.assertIn("Дата выдачи документа еще не наступила", page)
        self.assertIn('value="Брауни"', page)
        self.assertRegex(page, r'value="1000000840"\s+selected')
        self.assertRegex(page, r'value="8"\s+selected')
        self.assertRegex(page, r'value="1000000004"\s+selected')
