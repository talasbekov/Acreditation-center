"""P2: замер страниц на синтетических данных — число SQL и время рендера.

Размеры: S (1 заявка × 10 участников), M (10 × 10), L (100 × 30 = 3000 участников).
Запуск из корня редакции (PowerShell):
    $env:PYTHONPATH = "scripts"; $env:PERF_TAG = "after"
    python manage.py test perf_pages --settings=eventproject.settings_test
Результат — scripts/perf_result_<tag>.json (в репозиторий не добавлять).
"""
import json
import os
import statistics
import time
from datetime import date, timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from directories.models import City, Country, DocumentType, Sex
from eventproject.models import Attendee, Category, Event, Operator, Request

TAG = os.environ.get("PERF_TAG", "before")
OUT = Path(__file__).resolve().parent / f"perf_result_{TAG}.json"
REPEATS = int(os.environ.get("PERF_REPEATS", "7"))

SIZES = {"S": (1, 10), "M": (10, 10), "L": (100, 30), "B": (1, 300)}
EXTRA_OPERATORS = {"S": 2, "M": 10, "L": 50, "B": 2}


def directories():
    """Справочники в рабочем объёме: ~250 стран, 10 типов документов, 3 пола, 20 городов, 15 категорий."""
    from directories.models import Category as DirCategory
    Country.objects.bulk_create(
        [Country(country_code=f"1000000{i:03}", name_kaz=f"Ел{i}", name_rus=f"Страна{i}", name_eng=f"Country{i}",
                 country_iso=f"C{i}") for i in range(1, 251)]
    )
    DocumentType.objects.bulk_create(
        [DocumentType(doc_code=f"100000000{i}", name_kaz=f"Құжат{i}", name_rus=f"Документ{i}", name_eng=f"Doc{i}")
         for i in range(10)]
    )
    Sex.objects.bulk_create([Sex(sex_code=str(i), name_kaz=f"Ж{i}", name_rus=f"Пол{i}", name_eng=f"Sex{i}") for i in range(1, 4)])
    City.objects.bulk_create(
        [City(city_code=str(i), index=str(i), name_kaz=f"Қ{i}", name_rus=f"Город{i}", name_eng=f"City{i}") for i in range(1, 21)]
    )
    DirCategory.objects.bulk_create(
        [DirCategory(category_code=str(i), index=str(i), name_kaz=f"С{i}", name_rus=f"Кат{i}", name_eng=f"Cat{i}")
         for i in range(1, 16)]
    )


def build(size):
    n_req, per_req = SIZES[size]
    today = date.today()
    event = Event.objects.create(
        name_rus="Перф", name_kaz="Перф", name_eng="Perf", title="Perf", event_code="P",
        date_start=today, date_end=today + timedelta(days=30), city_code="1",
    )
    other = Event.objects.create(name_rus="Другое", title="Other", date_start=today, date_end=today + timedelta(days=10))
    cat = Category.objects.create(event=event, name="Охрана")
    op_user = User.objects.create_user("op", password="x", first_name="Опер", last_name="Атор")
    operator = Operator.objects.create(user=op_user, role="operator", patronymic="О", phone_number="+7000")
    operator.events.add(event, other)
    sup_user = User.objects.create_user("sup", password="x")
    sup = Operator.objects.create(user=sup_user, role="superoperator", patronymic="С", phone_number="+7001")
    sup.events.add(event)
    for i in range(EXTRA_OPERATORS[size]):
        u = User.objects.create_user(f"extra{i}", password="x", first_name=f"И{i}", last_name=f"Ф{i}")
        o = Operator.objects.create(user=u, role="operator", patronymic="Х", phone_number=f"+71{i}")
        if i % 2:
            o.events.add(event)
    admin = User.objects.create_superuser("admin", password="x")
    now = timezone.now()
    statuses = ["Active", "Sent", "Sent", "Exported"]
    reqs = Request.objects.bulk_create([
        Request(name=f"R{i}", event=event, status=statuses[i % 4], created_by=operator,
                registration_time=now, date_created=now - timedelta(minutes=i))
        for i in range(n_req)
    ])
    att_status = ["draft", "submitted", "in_review", "ready", "exported"]
    rows = []
    for r_i, req in enumerate(reqs):
        for a in range(per_req):
            k = r_i * per_req + a
            rows.append(Attendee(
                surname=f"Фамилия{k}", firstname="Имя", patronymic="", birthDate=date(1990, 1, 1),
                post="Инженер", countryId=f"1000000{(k % 250) + 1:03}", docTypeId="1000000002", docSeries="",
                stickId=str((k % 15) + 1),
                docNumber=f"N{k:07}", docBegin=date(2020, 1, 1), docEnd=date(2034, 1, 1), docIssue="Госдеп",
                photo=f"event_{event.pk}/attendee_photos/p{k}.jpg",
                docScan=f"event_{event.pk}/attendee_documents/d{k}.jpg",
                sexId="1", dateAdd=now - timedelta(seconds=k), visitObjects="Зал", transcription="FAMILIYA IMYA",
                request=req, category=cat, is_resident=False, status=att_status[k % 5],
                review_comment="Причина" if k % 7 == 0 and k % 5 == 0 else "",
            ))
    Attendee.objects.bulk_create(rows, batch_size=500)
    return {"event": event, "req": reqs[0], "operator": operator, "op_user": op_user,
            "sup_user": sup_user, "admin": admin}


def pages(d):
    e, r, o = d["event"].pk, d["req"].pk, d["operator"].pk
    return [
        ("op", "operator_cabinet", "get", "/application/"),
        ("op", "request_ru", "get", f"/show/{r}/"),
        ("op", "request_kz", "get", f"/kz/show/{r}/"),
        ("op", "request_en", "get", f"/en/show/{r}/"),
        ("op", "preview_ru", "get", f"/preview/{r}/"),
        ("op", "api_attendees_50", "get", "/api/v1/attendees/?page_size=50"),
        ("op", "api_requests", "get", "/api/v1/requests/?page_size=500"),
        ("admin", "admin_index", "get", "/avmac/"),
        ("admin", "admin_event", "get", f"/show_event/{e}/"),
        ("admin", "admin_request", "get", f"/show_request_to_admin/{r}/"),
        ("admin", "admin_operator", "get", f"/show_operator/{o}/"),
        ("sup", "dashboard", "get", f"/dashboard/{e}/"),
        ("sup", "review_queue", "get", f"/review/{e}/"),
        ("admin", "json_event", "post", f"/download_json/{e}/"),
    ]


@override_settings(DEBUG=False)
class PerfPages(TestCase):
    def _measure(self, size):
        d = build(size)
        users = {"op": d["op_user"], "sup": d["sup_user"], "admin": d["admin"]}
        out = {}
        for who, name, method, url in pages(d):
            self.client.force_login(users[who])
            call = getattr(self.client, method)
            first = call(url)  # прогрев (кеш дашборда и т. п.)
            times, counts = [], []
            for _ in range(REPEATS):
                if name == "dashboard":
                    from django.core.cache import cache
                    cache.clear()  # холодный дашборд — худший случай
                with CaptureQueriesContext(connection) as ctx:
                    t0 = time.perf_counter()
                    resp = call(url)
                    body = b"".join(resp.streaming_content) if resp.streaming else resp.content
                    times.append((time.perf_counter() - t0) * 1000)
                counts.append(len(ctx.captured_queries))
            out[name] = {
                "status": resp.status_code, "first_status": first.status_code,
                "sql": statistics.median(counts), "sql_max": max(counts),
                "ms_p50": round(statistics.median(times), 2), "ms_max": round(max(times), 2),
                "bytes": len(body),
            }
        return out

    def test_sizes(self):
        directories()
        print("countries", Country.objects.count(), "doctypes", DocumentType.objects.count(),
              "sexes", Sex.objects.count(), "cities", City.objects.count())
        result = {}
        for size in SIZES:
            with self.subTest(size=size):
                sid = connection.savepoint()
                result[size] = self._measure(size)
                connection.savepoint_rollback(sid)
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        names = list(result["S"])
        print(f"{'page':22} " + " ".join(f"{s+' sql':>7} {s+' ms':>8}" for s in SIZES))
        for n in names:
            print(f"{n:22} " + " ".join(
                f"{result[s][n]['sql']:>7} {result[s][n]['ms_p50']:>8}" + ("" if result[s][n]["status"] in (200,) else f"[{result[s][n]['status']}]")
                for s in SIZES))
