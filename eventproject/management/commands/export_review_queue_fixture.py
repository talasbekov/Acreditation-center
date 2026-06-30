"""Story fe-3.1 — экспорт golden-fixture очереди проверки → frontend (граница языков).

Сериализатор `ReviewQueueSerializer` (Python) — единственный источник формы DTO; vitest
не импортирует `.py`. Эта команда прогоняет живой сериализатор на репрезентативных
in-memory заявках (без БД → детерминированно) и пишет закоммиченный
`frontend/src/api/__fixtures__/review-queue.sample.json` (envelope пагинации). FE-mock
ВЫВОДИТСЯ из него (один источник истины). Анти-дрейф гарантирует backend-тест
(`test_review_queue_contract.py`): свежий вывод == закоммиченный файл. Прецедент —
`export_error_codes.py` / `errors/samples.py` (Story fe-1.1).
"""

import json
from datetime import date, datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

# fe-3.3 review (P7): detail-фикстура содержит datetime → DRF рендерит в активной
# Django-таймзоне, поэтому байт-сверка `test_review_queue_contract` молча зависела бы
# от settings.TIME_ZONE машины. Пиним рендер к фиксированному +05:00 (как в коммите
# фикстуры, и совпадает с проектным Asia/Almaty) — и команда, и тест идут через
# build_detail_payload, так что обе детерминированы независимо от окружения.
_FIXTURE_TZ = dt_timezone(timedelta(hours=5))

from eventproject.models import Attendee, Event, Request
from eventproject.problem_flags import PROBLEM_FLAGS
from eventproject.serializers.review_queue import (
    ReviewQueueDetailSerializer,
    ReviewQueueSerializer,
)
from eventproject.state_machine import AttendeeStatus

OUTPUT_PATH = (
    Path(settings.BASE_DIR) / "frontend" / "src" / "api" / "__fixtures__" / "review-queue.sample.json"
)
# fe-3.3 — golden-fixture ЭКРАНА ДЕТАЛЕЙ (одиночный объект, не envelope).
DETAIL_OUTPUT_PATH = (
    Path(settings.BASE_DIR) / "frontend" / "src" / "api" / "__fixtures__" / "review-queue-detail.sample.json"
)


def _attendee(*, id, surname, firstname, patronymic, iin, status, problem_flags, event=None):
    """In-memory заявка (НЕ сохраняется) с привязанным request/event для DTO-полей."""
    a = Attendee(
        id=id,
        surname=surname,
        firstname=firstname,
        patronymic=patronymic,
        iin=iin,
        status=status,
        problem_flags=problem_flags,
    )
    if event is not None:
        # request_id/event_id заполняются присваиванием инстансов с явными pk.
        a.request = Request(id=id, event=event)
    return a


def _sample_attendees():
    presscenter = Event(id=5, name_rus="Пресс-центр")
    mainhall = Event(id=6, name_rus="Главный зал")
    return [
        # Резидент, нет фото → флаг no_photo; submitted; sub_event задан.
        _attendee(
            id=101, surname="Алиев", firstname="Бахыт", patronymic="Серикулы",
            iin="851205301234", status=AttendeeStatus.SUBMITTED,
            problem_flags=["no_photo"], event=presscenter,
        ),
        # Чистая заявка in_review; sub_event задан; флагов нет.
        _attendee(
            id=102, surname="Иванова", firstname="Мария", patronymic="",
            iin="010314600078", status=AttendeeStatus.IN_REVIEW,
            problem_flags=[], event=mainhall,
        ),
        # Нет request → sub_event_id/name = null (защитная nullability контракта);
        # problem_flags = ВЕСЬ закрытый набор → представимость каждого члена enum в DTO.
        _attendee(
            id=103, surname="Нурланов", firstname="Тимур", patronymic="Асланулы",
            iin="900515312349", status=AttendeeStatus.SUBMITTED,
            problem_flags=list(PROBLEM_FLAGS), event=None,
        ),
    ]


def build_payload():
    """Детерминированный envelope пагинации с DTO от живого сериализатора (без БД)."""
    results = [ReviewQueueSerializer(a).data for a in _sample_attendees()]
    return {
        "count": len(results),
        "next": None,
        "previous": None,
        "results": results,
    }


def _detail_attendee():
    """In-memory заявка для detail-фикстуры (детерминированно, без БД/request-контекста).

    Фото/скан — фиксированные имена ImageField → `.url` = MEDIA_URL + path (относительный,
    детерминирован без request). Identity-поля заданы явно. ИИН маскируется сериализатором.
    """
    presscenter = Event(id=5, name_rus="Пресс-центр")
    a = Attendee(
        id=101,
        surname="Алиев",
        firstname="Бахыт",
        patronymic="Серикулы",
        iin="851205301234",
        status=AttendeeStatus.IN_REVIEW,
        problem_flags=["no_photo"],
        birthDate=date(1985, 12, 5),
        is_resident=True,
        countryId="Казахстан",
        post="Корреспондент",
        transcription="Aliyev Bakhyt Serikuly",
        docTypeId="passport",
        # Фиксированный aware-datetime → детерминированный ISO в фикстуре.
        dateAdd=datetime(2026, 6, 20, 9, 30, tzinfo=dt_timezone.utc),
    )
    a.request = Request(id=101, event=presscenter)
    a.photo = "event_5/attendee_photos/sample.jpg"
    a.docScan = "event_5/attendee_documents/sample.jpg"
    return a


def build_detail_payload():
    """Детерминированный DTO экрана деталей (одиночный объект) от живого сериализатора.

    Рендер datetime пиним к фиксированному +05:00 (P7) — иначе байт-сверка фикстуры
    зависела бы от settings.TIME_ZONE окружения.
    """
    with timezone.override(_FIXTURE_TZ):
        return ReviewQueueDetailSerializer(_detail_attendee()).data


def serialize(payload):
    """Канонический JSON (sort_keys + trailing newline) для байт-в-байт сравнения."""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


class Command(BaseCommand):
    help = (
        "Экспорт golden-fixture очереди проверки → "
        "frontend/src/api/__fixtures__/review-queue.sample.json (contract-тест zod↔DRF)."
    )

    def handle(self, *args, **options):
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        text = serialize(build_payload())
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Exported review-queue fixture → {OUTPUT_PATH}"))
        detail_text = serialize(build_detail_payload())
        DETAIL_OUTPUT_PATH.write_text(detail_text, encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(f"Exported review-queue DETAIL fixture → {DETAIL_OUTPUT_PATH}")
        )
