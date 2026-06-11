"""Наполнение e2e-базы: суперпользователь, оператор, событие, справочники.

Запуск: .venv/bin/python e2e/seed.py
"""
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventproject.settings_e2e")

import django

django.setup()

from django.contrib.auth.models import User
from directories.models import City, Country, DocumentType, Sex
from eventproject.models import Event, Operator

ADMIN = ("e2e_admin", "E2eAdminPass123!")
OPERATOR = ("e2e_operator", "E2eOperatorPass123!")


def main():
    admin, _ = User.objects.get_or_create(
        username=ADMIN[0],
        defaults={"is_superuser": True, "is_staff": True, "first_name": "Админ", "last_name": "Тестов"},
    )
    admin.is_superuser = True
    admin.is_staff = True
    admin.set_password(ADMIN[1])
    admin.save()

    op_user, _ = User.objects.get_or_create(
        username=OPERATOR[0],
        defaults={"first_name": "Оператор", "last_name": "Тестов"},
    )
    op_user.set_password(OPERATOR[1])
    op_user.save()
    operator, _ = Operator.objects.get_or_create(
        user=op_user,
        defaults={"patronymic": "Тестович", "phone_number": "+77001234567", "workplace": "E2E"},
    )

    # Кабинет оператора фильтрует по date_end в [сегодня; +600 дней] — даты обязательны
    from datetime import date, timedelta

    event, _ = Event.objects.get_or_create(
        event_code="E2E-001",
        defaults={
            "name_rus": "E2E Мероприятие",
            "name_kaz": "E2E Іс-шара",
            "name_eng": "E2E Event",
            "title": "E2E Мероприятие",
            "city_code": "1",
        },
    )
    event.date_start = date.today()
    event.date_end = date.today() + timedelta(days=30)
    event.save()
    operator.events.add(event)

    Sex.objects.get_or_create(sex_code="1", defaults={"name_rus": "Мужской", "name_kaz": "Ер", "name_eng": "Male"})
    Sex.objects.get_or_create(sex_code="2", defaults={"name_rus": "Женский", "name_kaz": "Әйел", "name_eng": "Female"})
    Country.objects.get_or_create(
        country_code="1000000105",
        defaults={"name_rus": "Казахстан", "name_kaz": "Қазақстан", "name_eng": "Kazakhstan",
                  "cis_flag": True, "country_iso": "KZ"},
    )
    DocumentType.objects.get_or_create(
        doc_code="1",
        defaults={"name_rus": "Паспорт", "name_kaz": "Паспорт", "name_eng": "Passport"},
    )
    City.objects.get_or_create(
        city_code="1",
        defaults={"index": "010000", "name_rus": "Астана", "name_kaz": "Астана", "name_eng": "Astana"},
    )

    print(f"seeded: admin={ADMIN[0]} operator={OPERATOR[0]} event_id={event.id}")


if __name__ == "__main__":
    main()
