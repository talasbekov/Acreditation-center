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
from django.db import IntegrityError, transaction
from django.utils.text import slugify
from text_unidecode import unidecode

from eventproject.models import Event, Operator

_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*"

# BE-8: username ограничен User.username max_length; усекаем base, оставляя место под
# числовой суффикс при коллизиях. Гонку уникальности переживаем savepoint+retry.
_USERNAME_MAX = User._meta.get_field("username").max_length
_USERNAME_SUFFIX_RESERVE = 12
_MAX_USERNAME_ATTEMPTS = 25


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
    # BE-8: усечь base, оставив место под суффикс — иначе длинная фамилия (unidecode
    # расширяет кириллицу) превысит max_length и даст ошибку БД.
    base = base[: _USERNAME_MAX - _USERNAME_SUFFIX_RESERVE]

    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{suffix}"
        suffix += 1
    return username[:_USERNAME_MAX]


def _create_user_unique(first_name, last_name, password, email):
    """BE-8: создаёт User, переживая гонку уникальности username.

    `generate_username` проверяет уникальность отдельным запросом — между проверкой и
    INSERT другой онбординг мог занять имя (IntegrityError → 500). Каждую попытку
    оборачиваем в savepoint (`transaction.atomic`), чтобы провал откатывал только её,
    и повторяем с перегенерированным суффиксом.
    """
    last_error = None
    for _ in range(_MAX_USERNAME_ATTEMPTS):
        username = generate_username(first_name, last_name)
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    username=username,
                    password=password,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
        except IntegrityError as exc:
            last_error = exc
    raise last_error


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
    user = _create_user_unique(first_name, last_name, temporary_password, email)
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
