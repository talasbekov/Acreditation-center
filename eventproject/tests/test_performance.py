"""P2 «Скорость»: число SQL не растёт с объёмом, справочники не перебираются на каждой строке,
статика не загружается повторно."""

import re
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.template import Context, Template
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from directories.models import Category as DirCategory, Country, DocumentType, Sex
from eventproject.models import Attendee, Event, Operator, Request


class Fixture(TestCase):
    def setUp(self):
        today = date.today()
        self.event = Event.objects.create(name_rus="E", title="E", date_start=today, date_end=today + timedelta(days=5))
        self.op_user = User.objects.create_user("op", password="x", first_name="Оп", last_name="Ер")
        self.operator = Operator.objects.create(user=self.op_user, role="operator", patronymic="О", phone_number="+7")
        self.operator.events.add(self.event)
        self.admin = User.objects.create_superuser("admin", password="x")
        Country.objects.create(country_code="1000000840", name_rus="США", name_kaz="АҚШ", name_eng="USA", country_iso="US")
        Country.objects.create(country_code="1000000250", name_rus="Франция", name_kaz="Франция", name_eng="France", country_iso="FR")
        Sex.objects.create(sex_code="1", name_rus="Мужской", name_kaz="Ер", name_eng="Male")
        DocumentType.objects.create(doc_code="1000000002", name_rus="Паспорт иностранца", name_kaz="Шетел паспорты", name_eng="Foreign passport")
        DirCategory.objects.create(category_code="7", index="7", name_rus="Пресса", name_kaz="Баспасөз", name_eng="Press")

    def _requests(self, count, attendees=1):
        now = timezone.now()
        reqs = []
        for i in range(count):
            req = Request.objects.create(name=f"R{i}", event=self.event, status="Sent" if i % 2 else "Active",
                                         created_by=self.operator, registration_time=now)
            for k in range(attendees):
                Attendee.objects.create(
                    surname=f"Ф{i}-{k}", firstname="И", post="P", countryId="1000000840", is_resident=False,
                    docTypeId="1000000002", docSeries="", docNumber=f"N{i}{k}", docIssue="X", sexId="1",
                    visitObjects="Z", transcription="T", request=req, dateAdd=now, stickId="7",
                )
            reqs.append(req)
        return reqs

    def _count(self, user, url):
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(ctx.captured_queries)


class QueryCountDoesNotGrowTests(Fixture):
    def _assert_flat(self, user, url_for):
        self._requests(2)
        small = self._count(user, url_for())
        self._requests(20)
        start = User.objects.count()
        Operator.objects.bulk_create([
            Operator(user=User.objects.create_user(f"x{start}-{i}", password="x"), patronymic="X", phone_number="+7")
            for i in range(10)
        ])
        self.assertEqual(self._count(user, url_for()), small, url_for())

    def test_operator_cabinet(self):
        for prefix in ("", "/kz", "/en"):
            with self.subTest(prefix=prefix):
                Request.objects.all().delete()
                self._assert_flat(self.op_user, lambda: f"{prefix}/application/")

    def test_admin_index(self):
        self._assert_flat(self.admin, lambda: "/avmac/")

    def test_admin_event_card(self):
        self._assert_flat(self.admin, lambda: f"/show_event/{self.event.pk}/")

    def test_admin_operator_card(self):
        self._assert_flat(self.admin, lambda: f"/show_operator/{self.operator.pk}/")

    def test_event_card_lists_operators_split(self):
        other = Operator.objects.create(user=User.objects.create_user("free", password="x", last_name="Свободный"),
                                        patronymic="С", phone_number="+7")
        self.client.force_login(self.admin)
        response = self.client.get(f"/show_event/{self.event.pk}/")
        self.assertEqual([o.pk for o in response.context["operators"]], [self.operator.pk])
        self.assertIn(other.pk, [o.pk for o in response.context["other_operators"]])
        self.assertNotIn(self.operator.pk, [o.pk for o in response.context["other_operators"]])


class DirectoryLabelTests(Fixture):
    def test_request_pages_show_directory_names(self):
        req = self._requests(1, attendees=3)[0]
        self.client.force_login(self.op_user)
        for prefix, words in (
            ("", ["Гражданство:</dt><dd>США", "Пол:</dt><dd>Мужской", "Категория:</dt><dd>Пресса", "Тип документа:</dt><dd>Паспорт иностранца"]),
            ("/kz", ["Азаматтығы:</dt><dd>АҚШ", "Жынысы:</dt><dd>Ер", "Категория:</dt><dd>Баспасөз", "Құжат түрі:</dt><dd>Шетел паспорты"]),
            ("/en", ["Citizenship:</dt><dd>USA", "Sex:</dt><dd>Male", "Category:</dt><dd>Press", "Document type:</dt><dd>Foreign passport"]),
        ):  # этап D: сведения участника — список dt/dd (отчёт 20)
            with self.subTest(prefix=prefix):
                page = self.client.get(f"{prefix}/show/{req.pk}/").content.decode()
                for word in words:
                    self.assertEqual(page.count(word), 3, word)
                self.assertNotIn("Франция", page)
                self.assertNotIn("France", page)
        self.client.force_login(self.admin)
        page = self.client.get(f"/show_request_to_admin/{req.pk}/").content.decode()
        self.assertEqual(page.count("США"), 3)
        self.assertEqual(page.count("Паспорт иностранца"), 3)

    def test_request_page_sql_does_not_depend_on_attendee_count(self):
        small = self._requests(1, attendees=2)[0]
        big = self._requests(1, attendees=30)[0]
        self.assertEqual(self._count(self.op_user, f"/show/{small.pk}/"), self._count(self.op_user, f"/show/{big.pk}/"))

    def test_dir_name_tag(self):
        template = Template(
            "{% load directory_tags %}{% for code in codes %}"
            "{% dir_name rows 'country_code' code 'name_eng' as n %}[{{ n }}]{% endfor %}"
        )
        rows = Country.objects.all()
        out = template.render(Context({"rows": rows, "codes": ["1000000840", "nope", "", None, "1000000250"]}))
        self.assertEqual(out, "[USA][][][][France]")


class StaticAssetsTests(Fixture):
    def _assets(self, html):
        return re.findall(r'<(?:script|link)[^>]+(?:src|href)="([^"]+\.(?:js|css))"', html)

    def test_no_duplicate_css_or_jquery(self):
        req = self._requests(1)[0]
        self.client.force_login(self.op_user)
        for url in ("/application/", f"/show/{req.pk}/", f"/add_attendee/{req.pk}/",
                    "/kz/application/", f"/kz/add_attendee/{req.pk}/", f"/en/add_attendee/{req.pk}/"):
            with self.subTest(url=url):
                assets = self._assets(self.client.get(url).content.decode())
                self.assertEqual(len(assets), len(set(assets)), assets)
                self.assertFalse(any("gov3.css" in a for a in assets), assets)
                self.assertLessEqual(sum("jquery" in a for a in assets), 1, assets)
                self.assertFalse(any("code.jquery.com" in a for a in assets), assets)

    def test_no_external_cdn(self):
        """Страницы работают без интернета: CSS/JS только из static/ (RU раньше тянул Bootstrap и jQuery с CDN)."""
        req = self._requests(1)[0]
        pages = [(self.op_user, u) for u in ("/application/", f"/show/{req.pk}/", f"/add_attendee/{req.pk}/",
                                             "/change_password/", "/kz/application/", "/en/application/")]
        pages.append((self.admin, "/avmac/"))
        for user, url in pages:
            with self.subTest(url=url):
                self.client.force_login(user)
                assets = self._assets(self.client.get(url).content.decode())
                self.assertTrue(assets, url)
                self.assertFalse([a for a in assets if a.startswith(("http:", "https:", "//"))], assets)
                self.assertTrue(any(a.endswith("css/bootstrap.min.css") for a in assets), assets)

    def test_attendee_images_are_lazy(self):
        req = self._requests(1)[0]
        Attendee.objects.filter(request=req).update(photo="p.jpg", docScan="d.jpg")
        self.client.force_login(self.op_user)
        for prefix in ("", "/kz", "/en"):
            page = self.client.get(f"{prefix}/show/{req.pk}/").content.decode()
            self.assertEqual(len(re.findall(r'<img loading="lazy"[^>]+/media/', page)), 2, prefix)


class AttendeeListIndexTests(TestCase):
    def test_date_index_declared(self):
        names = [index.name for index in Attendee._meta.indexes]
        self.assertIn("attendee_dateadd_idx", names)
