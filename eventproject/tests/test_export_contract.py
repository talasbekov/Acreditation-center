"""Story 4.1 — contract test для Integration Spec v1.0 (формат экспорта).

Проверяет, что объект attendee для downstream-экспорта соответствует ВСЕМ полям
машиночитаемой спеки `docs/integration-spec-v1.schema.json` (единый источник правды).
Тест ПАДАЕТ при любом отклонении формата — защита от регрессий (AC-3).

Здесь валидируется эталонный объект (фиксирует формат схемы). Реальный serializer
`build_export_object` валидируется против этой же схемы в
`test_export_delta.BuildExportObjectTests` (в т.ч. кейс с категорией — AC-6).

Формат v1.0 (утверждён Erda 2026-06-23): даты `DD.MM.YYYY`, datetime
`DD.MM.YYYY HH:MM:SS`, справочники отдаются как `*_id` + `*_name`.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

SPEC_SCHEMA_PATH = (
    Path(settings.BASE_DIR) / "docs" / "integration-spec-v1.schema.json"
)


def load_spec_schema():
    with open(SPEC_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _check_type(value, declared_type):
    """True, если value соответствует объявленному в спеке типу."""
    if declared_type == "integer":
        # bool — подкласс int в Python; для integer-поля bool недопустим.
        return isinstance(value, int) and not isinstance(value, bool)
    if declared_type == "boolean":
        return isinstance(value, bool)
    if declared_type == "string":
        return isinstance(value, str)
    if declared_type == "date":
        # Формат v1.0: DD.MM.YYYY (утверждён Erda 2026-06-23).
        if not isinstance(value, str):
            return False
        try:
            datetime.strptime(value, "%d.%m.%Y")
            return True
        except ValueError:
            return False
    if declared_type == "datetime":
        # Формат v1.0: DD.MM.YYYY HH:MM:SS.
        if not isinstance(value, str):
            return False
        try:
            datetime.strptime(value, "%d.%m.%Y %H:%M:%S")
            return True
        except ValueError:
            return False
    raise AssertionError(f"Неизвестный тип в спеке: {declared_type}")


def validate_against_spec(obj, schema):
    """Возвращает список ошибок (пустой = объект соответствует спеке)."""
    errors = []
    allowed = {f["name"] for f in schema["fields"]}

    # Неизвестные поля = отклонение формата (ловим дрейф).
    for key in obj:
        if key not in allowed:
            errors.append(f"неизвестное поле '{key}' (нет в спеке)")

    for field in schema["fields"]:
        name = field["name"]
        present = name in obj
        if not present:
            if field.get("required", False):
                errors.append(f"отсутствует обязательное поле '{name}'")
            continue

        value = obj[name]
        if value is None:
            if not field.get("nullable", False):
                errors.append(f"поле '{name}' = null, но nullable=false")
            continue

        if not _check_type(value, field["type"]):
            errors.append(
                f"поле '{name}': ожидался тип {field['type']}, получено {type(value).__name__}"
            )
            continue

        enum = field.get("enum")
        if enum is not None and value not in enum:
            errors.append(f"поле '{name}'={value!r} не входит в enum {enum}")

        pattern = field.get("pattern")
        if pattern is not None and isinstance(value, str) and not re.search(pattern, value):
            errors.append(f"поле '{name}'={value!r} не соответствует pattern {pattern}")

    return errors


def reference_attendee_object():
    """Эталонный валидный объект (из примера спеки). Story 4.3 заменит реальным serializer."""
    return {
        "attendee_id": 123,
        "event_id": 5,
        "event_code": "T1",
        "category": "Охрана",
        "status": "ready",
        "surname": "Иванов",
        "firstname": "Иван",
        "patronymic": "Петрович",
        "transcription": "Ivanov Ivan",
        "birth_date": "01.01.1990",
        "iin": "900101300007",
        "is_resident": True,
        "sex_id": "M",
        "sex_name": "Мужской",
        "country_id": "1000000105",
        "country_name": "Казахстан",
        "post": "Инженер",
        "doc_type_id": "passport",
        "doc_type_name": "Паспорт",
        "doc_series": "AA",
        "doc_number": "123456",
        "doc_begin": "01.01.2020",
        "doc_end": "01.01.2030",
        "doc_issue": "МВД",
        "visit_objects": "Объект A",
        "date_add": "23.06.2026 10:00:00",
        "photo_file": "photos/123.jpg",
        "doc_scan_file": "documents/123.jpg",
    }


class ExportContractTest(SimpleTestCase):
    """AC-3: contract test проверяет соответствие JSON-объекта спецификации."""

    def setUp(self):
        self.schema = load_spec_schema()

    def test_schema_file_loads_and_has_fields(self):
        self.assertIn("fields", self.schema)
        self.assertTrue(self.schema["fields"], "схема не содержит полей")

    def test_reference_object_matches_spec(self):
        errors = validate_against_spec(reference_attendee_object(), self.schema)
        self.assertEqual(errors, [], f"эталонный объект не соответствует спеке: {errors}")

    def test_nullable_fields_accept_null(self):
        # Нерезидент: iin=null, опциональные даты документа отсутствуют.
        obj = reference_attendee_object()
        obj["iin"] = None
        obj["patronymic"] = None
        errors = validate_against_spec(obj, self.schema)
        self.assertEqual(errors, [], f"nullable-поля должны принимать null: {errors}")

    def test_missing_required_field_fails(self):
        obj = reference_attendee_object()
        del obj["surname"]
        errors = validate_against_spec(obj, self.schema)
        self.assertTrue(any("surname" in e for e in errors))

    def test_wrong_type_fails(self):
        obj = reference_attendee_object()
        obj["attendee_id"] = "123"  # string вместо integer
        errors = validate_against_spec(obj, self.schema)
        self.assertTrue(any("attendee_id" in e for e in errors))

    def test_non_required_non_nullable_status_enum_enforced(self):
        obj = reference_attendee_object()
        obj["status"] = "draft"  # экспортируется только ready
        errors = validate_against_spec(obj, self.schema)
        self.assertTrue(any("status" in e for e in errors))

    def test_null_in_non_nullable_fails(self):
        obj = reference_attendee_object()
        obj["surname"] = None
        errors = validate_against_spec(obj, self.schema)
        self.assertTrue(any("surname" in e for e in errors))

    def test_unknown_field_flagged(self):
        obj = reference_attendee_object()
        obj["unexpected"] = "x"
        errors = validate_against_spec(obj, self.schema)
        self.assertTrue(any("unexpected" in e for e in errors))

    def test_media_path_pattern_enforced(self):
        obj = reference_attendee_object()
        obj["photo_file"] = "wrong/123.jpg"  # должно начинаться с photos/
        errors = validate_against_spec(obj, self.schema)
        self.assertTrue(any("photo_file" in e for e in errors))

    def test_iso_date_rejected(self):
        # Формат v1.0 — DD.MM.YYYY; ISO YYYY-MM-DD должен отклоняться (фиксация решения).
        obj = reference_attendee_object()
        obj["birth_date"] = "1990-01-01"
        errors = validate_against_spec(obj, self.schema)
        self.assertTrue(any("birth_date" in e for e in errors))

    def test_directory_name_fields_present_and_nullable(self):
        # Справочники отдаются как *_id + *_name; *_name nullable (код не найден → null).
        obj = reference_attendee_object()
        obj["country_name"] = None
        obj["sex_name"] = None
        obj["doc_type_name"] = None
        errors = validate_against_spec(obj, self.schema)
        self.assertEqual(errors, [], f"*_name должны принимать null: {errors}")
