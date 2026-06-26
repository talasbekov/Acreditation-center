"""Story fe-1.1 — экспорт реестра кодов ошибок → frontend (граница языков Python↔TS).

`errors/registry.py` (Python) — единственный источник; vitest не импортирует `.py`.
Эта команда сериализует реестр в закоммиченный `frontend/src/errors/errors.codes.json`,
который читает contract-тест zod↔DRF. Анти-дрейф гарантирует backend-тест
(`test_error_contract.py`): свежий вывод == закоммиченный файл. Прецедент committed-JSON —
`tests/test_export_contract.py` (Story 4.1).
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from eventproject.errors.registry import ERROR_CODES

OUTPUT_PATH = Path(settings.BASE_DIR) / "frontend" / "src" / "errors" / "errors.codes.json"


def build_payload():
    """Детерминированный payload реестра: code → {params: [...]}. Отсортировано."""
    return {
        code: {"params": list(spec.get("params", []))}
        for code, spec in sorted(ERROR_CODES.items())
    }


def serialize(payload):
    """Канонический JSON (sort_keys + trailing newline) для байт-в-байт сравнения."""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


class Command(BaseCommand):
    help = "Экспорт errors/registry.py → frontend/src/errors/errors.codes.json (для contract-теста zod↔DRF)."

    def handle(self, *args, **options):
        text = serialize(build_payload())
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(f"Exported {len(ERROR_CODES)} error codes → {OUTPUT_PATH}")
        )
