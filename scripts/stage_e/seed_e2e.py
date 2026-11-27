"""Синтетические данные сквозного сценария (см. README.md): учётные записи, справочники, файлы."""
import io
import os
import json
import secrets
from datetime import date, timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.utils import timezone
from PIL import Image

from directories.models import Category, Country, DocumentType, Sex
from eventproject.models import Event, Operator, Request

HERE = Path(os.environ["E2E_DIR"])

for code, ru, kz, en, iso in (("1000000105", "Казахстан", "Қазақстан", "Kazakhstan", "KZ"),
                              ("1000000840", "США", "АҚШ", "USA", "US")):
    Country.objects.get_or_create(country_code=code, defaults=dict(name_rus=ru, name_kaz=kz, name_eng=en, country_iso=iso))
Sex.objects.get_or_create(sex_code="1", defaults=dict(name_rus="Мужской", name_kaz="Ер", name_eng="Male"))
for code, ru in (("1000000001", "Удостоверение личности РК"), ("1000000002", "Паспорт иностранного гражданина"),
                 ("1000000003", "Паспорт РК")):
    DocumentType.objects.get_or_create(doc_code=code, defaults=dict(name_rus=ru, name_kaz=ru, name_eng=ru))
Category.objects.get_or_create(category_code="8", defaults=dict(index="8", name_rus="Гость", name_kaz="Қонақ", name_eng="Guest"))

today = date.today()
event = Event.objects.create(name_rus="Сквозное мероприятие", name_kaz="Сквозное мероприятие", name_eng="E2E event",
                             title="Сквозное мероприятие", event_code="E2E", date_start=today, date_end=today + timedelta(days=30))
creds = {}
for username, role in (("e2e_operator", "operator"), ("e2e_reviewer", "superoperator")):
    password = secrets.token_urlsafe(18)
    user = User.objects.create(username=username)
    user.set_password(password)
    user.save()
    op = Operator.objects.create(user=user, role=role, patronymic="Т", phone_number="+70000000000", workplace="E2E")
    op.events.add(event)
    creds[role] = {"username": username, "password": password}
operator = Operator.objects.get(user__username="e2e_operator")
req = Request.objects.create(name="E2E-01", event=event, status="Active", created_by=operator, registration_time=timezone.now())

files = HERE / "files"
files.mkdir(exist_ok=True)
b = io.BytesIO()
Image.new("RGB", (600, 800), (30, 110, 120)).save(b, "JPEG")
(files / "photo.jpg").write_bytes(b.getvalue())
b = io.BytesIO()
Image.new("RGB", (600, 800), (20, 40, 90)).save(b, "PDF", resolution=72)
(files / "scan.pdf").write_bytes(b.getvalue())

(HERE / "creds.json").write_text(json.dumps({**creds, "event": event.pk, "request": req.pk}), encoding="utf-8")
print("seeded event", event.pk, "request", req.pk)
