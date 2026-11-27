"""Поиск фото и сканов участников, на которые не ссылается ни одна запись.

По умолчанию только считает (имена файлов могут содержать ПД и не выводятся).
``--list`` печатает относительные пути, ``--delete`` удаляет найденное. Файлы
моложе ``--min-age-minutes`` пропускаются: они могут принадлежать записи,
которая ещё сохраняется.
"""

import os
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from eventproject.models import Attendee

_FOLDERS = ("attendee_photos", "attendee_documents")


class Command(BaseCommand):
    help = "Найти (и по флагу удалить) файлы участников без записи в БД"

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="удалить найденные файлы")
        parser.add_argument("--list", action="store_true", help="вывести относительные пути")
        parser.add_argument("--min-age-minutes", type=int, default=60)

    def handle(self, *args, **options):
        root = Path(settings.MEDIA_ROOT)
        referenced = set()
        for photo, scan in Attendee.objects.values_list("photo", "docScan").iterator():
            referenced.update(name for name in (photo, scan) if name)

        cutoff = time.time() - options["min_age_minutes"] * 60
        orphans = []
        for event_dir in sorted(root.glob("event_*")):
            for folder in _FOLDERS:
                for path in sorted((event_dir / folder).glob("*")):
                    if not path.is_file():
                        continue
                    relative = path.relative_to(root).as_posix()
                    if relative in referenced or path.stat().st_mtime > cutoff:
                        continue
                    orphans.append(path)

        size = sum(path.stat().st_size for path in orphans)
        if options["list"]:
            for path in orphans:
                self.stdout.write(path.relative_to(root).as_posix())
        if options["delete"]:
            for path in orphans:
                os.remove(path)
            self.stdout.write(f"Удалено файлов без записи: {len(orphans)}, {size} байт")
        else:
            self.stdout.write(f"Найдено файлов без записи: {len(orphans)}, {size} байт (ничего не удалено)")
