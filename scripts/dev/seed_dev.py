"""Демо-данные для локальной разработки web/ (только settings_dev, SQLite в .dev/).

    DJANGO_SETTINGS_MODULE=eventproject.settings_dev python manage.py migrate
    DJANGO_SETTINGS_MODULE=eventproject.settings_dev python scripts/dev/seed_dev.py

Справочники — из боевых CSV в scripts/ (те же коды СГО, что на сервере). Учётки
разработки (пароль `dev-pass-2026` у всех): admin (суперпользователь), superop
(супероператор), operator1, operator2 (операторы). Повторный запуск ничего не
дублирует: мероприятия и участники создаются, только если их ещё нет.
"""

import csv
import io
import os
import pathlib
import random
import sys
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventproject.settings_dev")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.core.files.base import ContentFile  # noqa: E402
from django.utils import timezone  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from directories.models import Category as Stick, City, Country, DocumentType, Sex  # noqa: E402
from eventproject.models import Attendee, Category, Event, Operator, Request  # noqa: E402
from eventproject.validators.iin import _control_digit  # noqa: E402

assert "sqlite" in settings.DATABASES["default"]["ENGINE"], "seed_dev только для settings_dev"

PASSWORD = "dev-pass-2026"
SCRIPTS = ROOT / "scripts"
random.seed(7)


def load_directories():
    with open(SCRIPTS / "countries.csv", encoding="utf-8") as f:
        for row in csv.reader(f):
            Country.objects.update_or_create(
                country_code=row[1],
                defaults=dict(name_rus=row[3], name_kaz=row[4], name_eng=row[7], cis_flag=row[8]),
            )
    with open(SCRIPTS / "docs.csv", encoding="utf-8") as f:
        for row in csv.reader(f, delimiter=";"):
            DocumentType.objects.update_or_create(
                doc_code=row[1], defaults=dict(name_rus=row[3], name_kaz=row[4], name_eng=row[5])
            )
    with open(SCRIPTS / "cities.csv", encoding="utf-8") as f:
        for row in csv.reader(f):
            City.objects.update_or_create(
                city_code=row[1], defaults=dict(index=row[2], name_rus=row[3], name_kaz=row[4], name_eng=row[5])
            )
    with open(SCRIPTS / "categories.csv", encoding="utf-8") as f:
        for row in csv.reader(f):
            Stick.objects.update_or_create(
                category_code=row[0], defaults=dict(index=row[1], name_rus=row[2], name_kaz=row[3], name_eng=row[4])
            )
    for code, ru, kz, en in (("1000000001", "Мужской", "Ер", "Male"), ("1000000002", "Женский", "Әйел", "Female")):
        Sex.objects.update_or_create(sex_code=code, defaults=dict(name_rus=ru, name_kaz=kz, name_eng=en))


def account(username, role, first, last, superuser=False):
    user, _ = User.objects.get_or_create(username=username)
    user.first_name, user.last_name = first, last
    user.email = f"{username}@dev.invalid"
    user.is_superuser = user.is_staff = superuser
    user.set_password(PASSWORD)
    user.save()
    op, _ = Operator.objects.get_or_create(
        user=user, defaults=dict(patronymic="", phone_number="+77000000000", workplace="Демо")
    )
    op.role, op.force_password_change = role, False
    op.save()
    return op


def iin_for(birth, male, serial):
    century = 3 if birth.year < 2000 else 5
    if not male:
        century += 1
    for tail in range(serial, serial + 50):
        head = f"{birth:%y%m%d}{century}{tail % 10000:04d}"
        digits = [int(c) for c in head]
        control = _control_digit(digits)
        if control is not None:
            return head + str(control)
    raise RuntimeError("no IIN")


def jpeg(text, color, size=(600, 800)):
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, size[0] - 40, size[1] - 40], outline="white", width=6)
    draw.text((80, size[1] // 2), text, fill="white")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def seed_events(superop, operators):
    if Event.objects.filter(event_code="AIF26").exists():
        return 0
    today = date.today()
    ev1 = Event.objects.create(
        name_rus="Астанинский международный форум", name_kaz="Астана халықаралық форумы",
        name_eng="Astana International Forum", title="AIF 2026", event_code="AIF26", city_code="1110106945",
        start_date=today + timedelta(days=10), end_date=today + timedelta(days=12),
        date_start=today + timedelta(days=10), date_end=today + timedelta(days=12), created_by=superop.user,
    )
    ev2 = Event.objects.create(
        name_rus="Выставка «Энергия»", name_kaz="«Энергия» көрмесі", name_eng="Energy Expo", title="Energy Expo",
        event_code="EXPO26", city_code="1110106946",
        start_date=today + timedelta(days=30), end_date=today + timedelta(days=33),
        date_start=today + timedelta(days=30), date_end=today + timedelta(days=33), created_by=superop.user,
    )
    for op in operators:
        op.events.add(ev1, ev2)

    surnames = ["Ахметов", "Смагулова", "Иванов", "Бекова", "Нурланов", "Ким", "Петрова", "Сейткали"]
    names = ["Асхат", "Мадина", "Сергей", "Айжан", "Ерлан", "Виктор", "Ольга", "Дамир"]
    colors = ["#2a6f97", "#6a4c93", "#1b998b", "#c44536", "#3d5a80", "#8a5a44"]
    sticks = list(Stick.objects.values_list("category_code", flat=True))
    n = 0
    for ev, cats in ((ev1, ["Делегаты", "Пресса"]), (ev2, ["Экспоненты"])):
        for cname in cats:
            cat = Category.objects.create(event=ev, name=cname)
            for creator, req_status, statuses in (
                (operators[1], "Active", ["draft", "draft", "draft"]),
                (operators[2], "Sent", ["submitted", "in_review", "ready", "ready"]),
            ):
                req = Request.objects.create(
                    name=f"{timezone.now():%d%m%Y%H%M%S}{n}", event=ev, status=req_status,
                    created_by=creator, registration_time=timezone.now(),
                )
                for st in statuses:
                    n += 1
                    foreign = n % 4 == 0
                    male = n % 2 == 0
                    birth = date(1975 + n % 25, 1 + n % 12, 1 + n % 27)
                    sur, first = random.choice(surnames), random.choice(names)
                    a = Attendee(
                        surname=sur, firstname=first, patronymic="", birthDate=birth,
                        post=random.choice(["Директор", "Журналист", "Инженер", "Советник"]),
                        countryId="1000000224" if foreign else settings.KZ_COUNTRY_ID,
                        docTypeId="1000000002" if foreign else "1000000003",
                        docSeries="N" if foreign else "", docNumber=f"{100000 + n}",
                        docIssue="US DoS" if foreign else "МВД РК",
                        docBegin=today - timedelta(days=900), docEnd=today + timedelta(days=2000),
                        iin=None if foreign else iin_for(birth, male, n * 7),
                        sexId="1000000001" if male else "1000000002",
                        stickId="" if not foreign else random.choice(sticks),
                        dateAdd=timezone.now(), dateEnd=ev.end_date, visitObjects="Главный зал",
                        transcription=f"{sur} {first}".upper(), request=req, category=cat,
                        status=st, is_resident=not foreign,
                    )
                    a.photo.save(f"photo_{n}.jpg", ContentFile(jpeg(f"{sur} {first}", random.choice(colors))), save=False)
                    a.docScan.save(f"doc_{n}.jpg", ContentFile(jpeg(f"DOC {a.docNumber}", "#555555")), save=False)
                    a.save()
    return n


if __name__ == "__main__":
    load_directories()
    superop = account("superop", "superoperator", "Айгерим", "Супероператор")
    account("admin", "superuser", "Админ", "Демо", superuser=True)
    ops = [superop, account("operator1", "operator", "Ержан", "Оператор"), account("operator2", "operator", "Дана", "Оператор")]
    print(f"seeded attendees: {seed_events(superop, ops)}")
