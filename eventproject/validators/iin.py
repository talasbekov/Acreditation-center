"""ИИН — единственный Python-источник правды (Story 3.1).

Содержит нормализацию/маскирование/дедуп (Story 1.2/1.x) и канонический
валидатор `validate_iin` (формат + контрольная цифра + дата рождения).
DRF serializers (3.4) и legacy UI (3.5) ВЫЗЫВАЮТ этот модуль, не дублируют
алгоритм. TypeScript-дубликат — отдельный источник в Epic 5.
"""

from dataclasses import dataclass
from datetime import date

# Веса контрольной цифры: первый проход и fallback при остатке 10.
_WEIGHTS_1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
_WEIGHTS_2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
# Позиция 7 ИИН → базовый век рождения (нечётная цифра — муж, чётная — жен).
_CENTURY_BASE = {1: 1800, 2: 1800, 3: 1900, 4: 1900, 5: 2000, 6: 2000}

_ERR_FORMAT = "ИИН должен содержать ровно 12 цифр."
_ERR_CONTROL = "ИИН некорректен: неверная контрольная цифра."
_ERR_DATE_INVALID = "ИИН некорректен: недопустимая дата рождения."


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error: str = ""


def normalize_iin(value):
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def mask_iin(value):
    """Маскирует ИИН для логов/экспортов: видны только последние 4 цифры."""
    normalized = normalize_iin(value)
    if not normalized:
        return ""
    return "********" + normalized[-4:]


def event_has_iin_duplicate(attendees, iin, exclude_pk=None):
    normalized_iin = normalize_iin(iin)
    if not normalized_iin:
        return False

    for attendee in attendees.only("pk", "iin"):
        if exclude_pk is not None and attendee.pk == exclude_pk:
            continue
        if normalize_iin(attendee.iin) == normalized_iin:
            return True

    return False


def _format_date(value):
    """ДД.ММ.ГГГГ с ведущими нулями (FR23)."""
    return f"{value.day:02d}.{value.month:02d}.{value.year:04d}"


def _control_digit(digits):
    """Контрольная цифра по первым 11 цифрам ИИН.

    Возвращает int 0–9 либо None, если валидной контрольной цифры не существует
    (оба прохода дают остаток 10).
    """
    control = sum(digits[i] * _WEIGHTS_1[i] for i in range(11)) % 11
    if control == 10:
        control = sum(digits[i] * _WEIGHTS_2[i] for i in range(11)) % 11
        if control == 10:
            return None
    return control


def validate_iin(iin, birth_date):
    """Валидация казахстанского ИИН (Story 3.1).

    iin        — строка из 12 цифр, либо None/пусто для нерезидента.
    birth_date — datetime.date (введённая дата рождения); может быть None.

    Порядок проверок: нерезидент → формат → контрольная цифра → дата рождения.
    Возвращает ValidationResult(valid, error). Сообщения — дословно по FR23/AC.
    """
    normalized = normalize_iin(iin)
    if normalized is None:
        # Нерезидент / ИИН не задан — проверка ИИН не выполняется (AC-5).
        return ValidationResult(valid=True)

    if len(normalized) != 12 or any(ch not in "0123456789" for ch in normalized):
        return ValidationResult(valid=False, error=_ERR_FORMAT)

    digits = [int(ch) for ch in normalized]

    control = _control_digit(digits)
    if control is None or control != digits[11]:
        return ValidationResult(valid=False, error=_ERR_CONTROL)

    # Дата рождения: позиции 1–6 (YYMMDD) + век из позиции 7.
    century = _CENTURY_BASE.get(digits[6])
    if century is None:
        return ValidationResult(valid=False, error=_ERR_DATE_INVALID)
    year = century + digits[0] * 10 + digits[1]
    month = digits[2] * 10 + digits[3]
    day = digits[4] * 10 + digits[5]
    try:
        iin_date = date(year, month, day)
    except ValueError:
        # Недопустимая календарная дата в ИИН (напр. 30 февраля, 13-й месяц).
        return ValidationResult(valid=False, error=_ERR_DATE_INVALID)

    # birth_date может отсутствовать (защитно): тогда сравнение пропускаем.
    # Сравниваем по (год, месяц, день) — устойчиво и к date, и к datetime
    # (в Python `date != datetime` всегда True, что давало ложное «не совпадает»).
    if birth_date is not None and (
        (iin_date.year, iin_date.month, iin_date.day)
        != (birth_date.year, birth_date.month, birth_date.day)
    ):
        return ValidationResult(
            valid=False,
            error=(
                f"Дата рождения в ИИН ({_format_date(iin_date)}) не совпадает "
                f"с введённой ({_format_date(birth_date)}). Проверьте дату."
            ),
        )

    return ValidationResult(valid=True)
