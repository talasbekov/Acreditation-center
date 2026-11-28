"""Экспорт текстов интерфейса старой АЦ в Next.js (`web/lib/generated/`).

Новый интерфейс берёт переводы из тех же источников, что и HTML-страницы, чтобы
формулировки совпадали дословно:

* `ui-text.json` — словарь `ui_text.UI` (ключ — русская строка, значения kz/en);
* `messages.json` — сообщения `page_lang._TEXT` (ключ → ru/kz/en);
* `errors.json` — тексты машинных кодов ошибок API (`frontend/src/errors/errors.json`).

Файлы закоммичены; `tests/test_web_texts.py` проверяет, что они совпадают со свежим
выводом этой команды.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from eventproject import page_lang
from eventproject.ui_text import UI

OUTPUT_DIR = Path(settings.BASE_DIR) / "web" / "lib" / "generated"
ERRORS_SOURCE = Path(settings.BASE_DIR) / "frontend" / "src" / "errors" / "errors.json"


def serialize(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_files():
    """Имя файла → текст. Детерминированно (sort_keys)."""
    errors = json.loads(ERRORS_SOURCE.read_text(encoding="utf-8"))
    return {
        "ui-text.json": serialize(UI),
        "messages.json": serialize(page_lang._TEXT),
        "errors.json": serialize(errors),
    }


class Command(BaseCommand):
    help = "Экспорт ui_text.UI, page_lang._TEXT и errors.json в web/lib/generated/."

    def handle(self, *args, **options):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for name, text in build_files().items():
            (OUTPUT_DIR / name).write_text(text, encoding="utf-8", newline="\n")
        self.stdout.write(f"Exported web texts to {OUTPUT_DIR}")
