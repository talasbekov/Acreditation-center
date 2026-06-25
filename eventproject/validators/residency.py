"""Residency-логика — единственный источник правды (Story 3.2).

Определяет резидентство по `Attendee.countryId` и применяет правила ИИН:
резидент РК → ИИН обязателен и валиден (через validators/iin.py);
нерезидент → ИИН не требуется и нормализуется в None (в БД NULL).

DRF serializer (3.4) и legacy-форма (3.5) ВЫЗЫВАЮТ этот модуль, не дублируют
логику. ИИН-алгоритм не копируется — используется validate_iin (3.1).
"""

from dataclasses import dataclass

from django.conf import settings

from eventproject.validators.iin import normalize_iin, validate_iin

_DEFAULT_KZ_COUNTRY_ID = "1000000105"

_ERR_IIN_REQUIRED = "ИИН обязателен для граждан Казахстана"


def _kz_country_id():
    # .strip() симметрично нормализации входа в is_resident_country — иначе
    # пробел в env-значении KZ_COUNTRY_ID молча превратит всех резидентов в нерезидентов.
    return str(getattr(settings, "KZ_COUNTRY_ID", _DEFAULT_KZ_COUNTRY_ID)).strip()


def is_resident_country(country_id) -> bool:
    """True, если страна соответствует идентификатору Казахстана (резидент РК)."""
    if country_id is None:
        return False
    return str(country_id).strip() == _kz_country_id()


def is_known_country(country_id) -> bool:
    """True, если country_id известен: резидент РК (KZ-id) ИЛИ есть в справочнике.

    BE-5: `Country.country_code` — авторитетный маппинг `Attendee.countryId`
    (см. `services/export.py`). Нужен, чтобы непустой, но малформ/неизвестный
    countryId (напр. «1000000105aaaa») не трактовался молча как нерезидент с
    отбросом ИИН. БД-доступ: вызывать из слоёв с БД (serializer/view), НЕ из
    pure-логики `resolve_residency` (она остаётся без ORM, SimpleTestCase).
    """
    if is_resident_country(country_id):
        return True
    if country_id is None:
        return False
    from directories.models import Country

    return Country.objects.filter(country_code=str(country_id).strip()).exists()


@dataclass(frozen=True)
class ResidencyResult:
    is_resident: bool
    iin: object = None  # нормализованный ИИН (str для резидента) либо None
    error: str = ""


def resolve_residency(country_id, iin, birth_date) -> ResidencyResult:
    """Применяет residency-правила.

    Нерезидент → ИИН игнорируется (iin=None), ошибок нет.
    Резидент РК → ИИН обязателен; пустой → ошибка; иначе проверка через
    validate_iin(iin, birth_date) и его сообщение при невалидности.
    """
    if not is_resident_country(country_id):
        # Нерезидент: ИИН не хранится, даже если был передан (AC-3).
        return ResidencyResult(is_resident=False, iin=None)

    normalized = normalize_iin(iin)
    if normalized is None:
        return ResidencyResult(is_resident=True, iin=None, error=_ERR_IIN_REQUIRED)

    result = validate_iin(normalized, birth_date)
    if not result.valid:
        return ResidencyResult(is_resident=True, iin=normalized, error=result.error)

    return ResidencyResult(is_resident=True, iin=normalized)
