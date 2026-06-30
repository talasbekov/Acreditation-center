"""Story fe-1.1 — машинный реестр кодов ошибок (ЕДИНЫЙ источник правды).

Эту структуру читают: DRF `exception_handler` (api/exceptions.py), management-команда
`export_error_codes` (→ frontend/src/errors/errors.codes.json) и contract-тест zod↔DRF.
Фронтовый словарь `frontend/src/errors/errors.json` обязан иметь РОВНО те же ключи
(contract-тест проверяет равенство множеств). FR-UX-1 · UX-DR2 · architecture.md §R1-ревизия.

Коды — `snake_case`, плоские, неймспейс префиксом. `params` — имена ключей интерполяции
(пусто для большинства; динамические значения доносит `CodedValidationError`, см. __init__.py).
`detail` — дефолтная (ru) строка ТОЛЬКО для логов/не-UI потребителей (не источник UI-текста;
UI-текст рендерит React-маппер из errors.json, story fe-1.2).
"""

# code → {"field": дефолтное поле|None, "params": [имена ключей], "detail": ru-строка для логов}
ERROR_CODES = {
    # ── ИИН (validators/iin.py · residency.py) ──────────────────────────────
    "iin_format": {"field": "iin", "params": [], "detail": "ИИН должен содержать ровно 12 цифр."},
    "iin_checksum": {"field": "iin", "params": [], "detail": "ИИН некорректен: неверная контрольная цифра."},
    "iin_date_invalid": {"field": "iin", "params": [], "detail": "ИИН некорректен: недопустимая дата рождения."},
    "iin_dob_mismatch": {
        "field": "iin",
        "params": ["iin_dob", "entered_dob"],
        "detail": "Дата рождения в ИИН ({iin_dob}) не совпадает с введённой ({entered_dob}). Проверьте дату.",
    },
    "iin_required": {"field": "iin", "params": [], "detail": "ИИН обязателен для граждан Казахстана"},
    "duplicate_attendee": {"field": "iin", "params": [], "detail": "Участник с этим ИИН уже добавлен в это мероприятие."},
    "country_unknown": {"field": "countryId", "params": [], "detail": "Неизвестный код страны."},
    # ── Фото/документ (validators/photo.py) ─────────────────────────────────
    "photo_too_large": {"field": "photo", "params": [], "detail": "Файл слишком большой (максимум 5 МБ)"},
    "photo_ratio": {"field": "photo", "params": [], "detail": "Фото должно быть вертикальным (формат 3×4)"},
    "photo_low_res": {"field": "photo", "params": [], "detail": "Разрешение слишком низкое (минимум 600×800 пикселей)"},
    "photo_not_image": {"field": "photo", "params": [], "detail": "Файл не является изображением"},
    "photo_too_many_pixels": {"field": "photo", "params": [], "detail": "Изображение слишком большое (превышен лимит пикселей)"},
    "doc_unreadable": {"field": "docScan", "params": [], "detail": "Не удалось обработать PDF-документ"},
    # ── События/категории/операторы (serializers/event.py · operator.py) ────
    "category_name_blank": {"field": "name", "params": [], "detail": "Название категории не может быть пустым."},
    "event_date_inverted": {"field": "end_date", "params": [], "detail": "Дата окончания не может быть раньше даты начала."},
    "events_not_found": {"field": "event_ids", "params": ["missing"], "detail": "Мероприятия не найдены: {missing}"},
    "category_not_found": {"field": "category_id", "params": [], "detail": "Категория не найдена."},
    "email_exists": {"field": "email", "params": [], "detail": "Пользователь с таким email уже существует."},
    # ── Query-/state-параметры (views/attendee_api.py · operator_api.py) ─────
    "param_not_int": {"field": None, "params": [], "detail": "Должно быть целым числом."},
    "status_invalid": {"field": "status", "params": [], "detail": "Недопустимое значение статуса."},
    "status_transition_invalid": {"field": "status", "params": [], "detail": "Недопустимый переход статуса."},
    "email_status_invalid": {"field": "email_status", "params": [], "detail": "Недопустимое значение email_status."},
    "problem_invalid": {"field": "problem", "params": [], "detail": "Недопустимое значение фильтра проблемы."},
    # ── Иерархия событий (models.py Event.clean) ────────────────────────────
    "event_parent_self": {"field": "parent", "params": [], "detail": "Мероприятие не может быть своим родителем."},
    "event_parent_missing": {"field": "parent", "params": [], "detail": "Указанное родительское мероприятие не существует."},
    "event_hierarchy_depth": {"field": "parent", "params": [], "detail": "Иерархия мероприятий — ровно один уровень."},
    "event_dates_outside_parent": {"field": "start_date", "params": [], "detail": "Даты под-мероприятия должны быть в пределах дат родителя."},
    "container_name_required": {"field": "is_container", "params": [], "detail": "Контейнер-мероприятие обязано иметь название на ru/kz/en."},
    # ── Generic DRF-коды (авто-эмитятся встроенными field/relation-проверками) ──
    "required": {"field": None, "params": [], "detail": "Обязательное поле."},
    "invalid": {"field": None, "params": [], "detail": "Некорректное значение."},
    "blank": {"field": None, "params": [], "detail": "Поле не может быть пустым."},
    "null": {"field": None, "params": [], "detail": "Поле не может быть пустым."},
    "max_length": {"field": None, "params": [], "detail": "Слишком длинное значение."},
    "min_length": {"field": None, "params": [], "detail": "Слишком короткое значение."},
    "max_string_length": {"field": None, "params": [], "detail": "Слишком длинная строка."},
    "max_value": {"field": None, "params": [], "detail": "Значение слишком большое."},
    "min_value": {"field": None, "params": [], "detail": "Значение слишком маленькое."},
    "invalid_choice": {"field": None, "params": [], "detail": "Недопустимый выбор."},
    "does_not_exist": {"field": None, "params": [], "detail": "Объект не найден."},
    "incorrect_type": {"field": None, "params": [], "detail": "Некорректный тип значения."},
    "unique": {"field": None, "params": [], "detail": "Значение должно быть уникальным."},
    "empty": {"field": None, "params": [], "detail": "Поле не может быть пустым."},
    "date": {"field": None, "params": [], "detail": "Некорректная дата."},
    "datetime": {"field": None, "params": [], "detail": "Некорректные дата и время."},
    "permission_denied": {"field": None, "params": [], "detail": "Недостаточно прав для этого действия."},
    "not_found": {"field": None, "params": [], "detail": "Не найдено."},
    "not_authenticated": {"field": None, "params": [], "detail": "Требуется аутентификация."},
    "parse_error": {"field": None, "params": [], "detail": "Некорректный запрос."},
    # ── Catch-all (любой непомеченный/неизвестный код) ──────────────────────
    "unknown": {"field": None, "params": [], "detail": "Произошла ошибка. Повторите позже."},
}


def all_codes():
    """Множество всех кодов реестра (для contract-теста и export-команды)."""
    return set(ERROR_CODES)


def code_exists(code):
    return code in ERROR_CODES


def spec_for(code):
    """Спецификация кода (с fallback на ``unknown`` для незнакомого)."""
    return ERROR_CODES.get(code, ERROR_CODES["unknown"])
