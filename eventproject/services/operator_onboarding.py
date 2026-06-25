"""Story 2.3 — генерация учётных данных и создание оператора.

`make_random_password()` был удалён в Django 5.1, поэтому пароль генерируется через
`secrets` (криптостойкий) из сложного алфавита. Username строится из ФИО с
транслитерацией кириллицы (`text_unidecode`) и гарантией уникальности.

Создание `User` + `Operator` выполняется в `transaction.atomic()`. Отправка email
выполняется ВНЕ транзакции (вызывающим кодом), чтобы лаги SMTP не держали БД.
"""

import secrets
import string

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify
from text_unidecode import unidecode

from eventproject.models import Event, Operator

_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*"


def generate_password(length=12):
    """Криптостойкий временный пароль (минимум 12 символов) из сложного алфавита."""
    if length < 12:
        length = 12
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def generate_username(first_name, last_name):
    """Уникальный username вида `familiya.i` (транслит кириллицы), с суффиксом при коллизии."""
    last = slugify(unidecode(last_name or "")) or "operator"
    first_initial = slugify(unidecode(first_name or ""))[:1]
    base = f"{last}.{first_initial}" if first_initial else last

    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{suffix}"
        suffix += 1
    return username


@transaction.atomic
def create_operator(validated_data):
    """Создаёт `User` + `Operator` по валидированным данным.

    Возвращает кортеж `(operator, temporary_password)`. Email НЕ отправляется здесь —
    это делает вызывающий код после коммита транзакции.
    """
    first_name = validated_data["first_name"]
    last_name = validated_data["last_name"]
    patronymic = validated_data.get("patronymic", "") or ""
    email = validated_data["email"]
    event_ids = validated_data.get("event_ids") or []
    category_id = validated_data.get("category_id")

    temporary_password = generate_password()
    username = generate_username(first_name, last_name)

    user = User.objects.create_user(
        username=username,
        password=temporary_password,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    operator = Operator.objects.create(
        user=user,
        patronymic=patronymic,
        role="operator",
        force_password_change=True,
        email_status="pending",
        category_id=category_id,
    )
    if event_ids:
        operator.events.set(Event.objects.filter(id__in=event_ids))

    return operator, temporary_password
