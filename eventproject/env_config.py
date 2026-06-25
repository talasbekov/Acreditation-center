"""Хелперы загрузки настроек окружения (вынесены из settings.py для тестируемости).

- BE-6: `require_env` — собрать ВСЕ отсутствующие обязательные секреты и упасть
  одним понятным `ImproperlyConfigured`, а не криптичным per-var `UndefinedValueError`
  на первой же отсутствующей переменной.
- BE-15: `parse_bool_flag` — распознать булев токен; нераспознанное значение (typo
  «yess»/«enabled») не молча → False, а откат на default + сигнал «не распознано»,
  чтобы typo не отключал секьюрный флаг (напр. SECURE_SSL_REDIRECT default=True).

`config` передаётся параметром (DI) → модуль юнит-тестируем без импорта settings.py.
"""

from decouple import UndefinedValueError
from django.core.exceptions import ImproperlyConfigured

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off", ""}


def require_env(config, specs):
    """Загрузить обязательные env-переменные; одно исключение на ВСЕ отсутствующие.

    config — вызываемый объект уровня decouple `config(name, **kwargs)`.
    specs  — dict {ИМЯ: {доп. kwargs для config, напр. {"cast": Csv()}}}.
    Возвращает dict {ИМЯ: значение}. Если хоть одна отсутствует — ImproperlyConfigured
    со списком ВСЕХ отсутствующих (значения секретов в сообщение не попадают).
    """
    values = {}
    missing = []
    for name, kwargs in specs.items():
        try:
            values[name] = config(name, **kwargs)
        except UndefinedValueError:
            missing.append(name)
    if missing:
        raise ImproperlyConfigured(
            "Отсутствуют обязательные переменные окружения: "
            + ", ".join(missing)
            + ". Задайте их в окружении/.env перед запуском."
        )
    return values


def parse_bool_flag(raw, default):
    """Разобрать булев флаг из строки. Возвращает (value, recognized).

    recognized=False для нераспознанного токена → value=bool(default) (а не молча
    False), чтобы typo не флипал секьюрный дефолт. Вызывающий код решает, логировать ли.
    """
    token = str(raw).strip().lower()
    if token in _TRUTHY:
        return True, True
    if token in _FALSY:
        return False, True
    return bool(default), False
