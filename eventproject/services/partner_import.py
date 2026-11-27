"""Этап C — идемпотентный приём анкет партнёров (KazEnergy, Avalon/KazExpo).

Порядок для каждой анкеты:
1. Анкета с уже известным идентификатором не обрабатывается заново: партнёру
   повторно уходит сохранённое подтверждение (``PartnerReceipt.ack_payload``).
2. Новая анкета проверяется, сверяется с правилом дублей и записывается под
   блокировкой мероприятия вместе с квитанцией. Подтверждение (ACK) уходит
   только после записи.
3. Если подтверждение не доставлено, цикл останавливается: при следующем
   запуске партнёр пришлёт ту же анкету, и ей уйдёт то же подтверждение.

Фото и скан проходят те же правила, что в формах и API. Неподходящий файл не
сохраняется, анкета принимается черновиком без него, партнёру — успешный код с
пометкой (решение владельца 25.11.2026). Отправить такого участника на
проверку оператор не сможет, пока не загрузит файл.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from eventproject.models import Attendee, PartnerReceipt, Request
from eventproject.services import intake
from eventproject.validators.iin import normalize_iin
from eventproject.validators.residency import is_resident_country

logger = logging.getLogger("eventproject.partner_import")

_FILE_LABEL = {"photo": "Фото", "docScan": "Скан документа"}


class RecordError(Exception):
    """Анкету нельзя записать; текст уходит партнёру и не содержит значений полей."""


def _empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return stripped == "" or stripped.lower() == "null"
    return False


def _text(value):
    return "" if _empty(value) else str(value).strip()


def _date(record, name):
    value = record.get(name)
    if _empty(value):
        return None
    try:
        parsed = parse_date(str(value).strip())
    except ValueError:
        parsed = None
    if parsed is None:
        raise RecordError(f"Неверная дата в поле {name}")
    return parsed


def _moment(record, name):
    value = record.get(name)
    if _empty(value):
        return timezone.now()
    try:
        parsed = parse_datetime(str(value).strip())
    except ValueError:
        parsed = None
    if parsed is None:
        raise RecordError(f"Неверная дата в поле {name}")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


@dataclass(frozen=True)
class PartnerSource:
    """Контракт подтверждений конкретного партнёра (форматы прежних версий)."""

    name: str
    required: tuple
    missing_ack: Callable
    duplicate_ack: Callable
    success_ack: Callable
    failure_ack: Callable


def _with_note(payload, notes):
    if notes:
        payload["message"] = "; ".join(notes)
    return payload


KAZENERGY = PartnerSource(
    name="kazenergy",
    required=(
        "surname", "firstname", "post", "countryId", "docTypeId", "docNumber",
        "sexId", "visitObjects", "transcription", "dateAdd", "birthDate", "docBegin", "docEnd",
    ),
    missing_ack=lambda rid, missing: {"id": rid, "code": 9, "message": "Отсутствуют поля: " + ", ".join(missing)},
    # Прежний контракт: дубль подтверждается кодом 2, чтобы очередь его не возвращала.
    duplicate_ack=lambda rid: {"id": rid, "code": 2},
    success_ack=lambda rid, attendee, notes: _with_note({"id": rid, "code": 2}, notes),
    failure_ack=lambda rid, reason: {"id": rid, "code": 9, "message": reason},
)

AVALON = PartnerSource(
    name="avalon",
    required=(
        "surname", "firstname", "post", "countryId", "docTypeId", "sexId",
        "visitObjects", "transcription", "birthDate", "stickId",
    ),
    missing_ack=lambda rid, missing: {
        "id": rid, "code": 1, "message": ", ".join(f'null value in column "{name}"' for name in missing),
    },
    duplicate_ack=lambda rid: {"id": rid, "code": 1, "comment": "Дубликат"},
    success_ack=lambda rid, attendee, notes: _with_note(
        {"id": rid, "code": 2, "RECORD NUMBER": f"№{attendee.pk}"}, notes,
    ),
    failure_ack=lambda rid, reason: {
        "id": rid, "code": 1, "message": "Ошибка при сохранении участника", "error_detail": reason,
    },
)


def _external_key(record):
    raw = record.get("id")
    if _empty(raw) or isinstance(raw, (dict, list)):
        return None
    return str(raw).strip()[:128]


def _build_attendee(record):
    country = _text(record.get("countryId"))
    resident = is_resident_country(country)
    doc_end = _date(record, "docEnd")
    return Attendee(
        surname=_text(record.get("surname")),
        firstname=_text(record.get("firstname")),
        patronymic=_text(record.get("patronymic")),
        birthDate=_date(record, "birthDate"),
        post=_text(record.get("post")),
        countryId=country,
        docTypeId=_text(record.get("docTypeId")),
        docSeries=_text(record.get("docSeries")),
        # Нерезидент: ИИН не хранится (как в формах и API). Ошибку ИИН резидента
        # покажет проверка при отправке заявки.
        iin=normalize_iin(record.get("iin")) if resident else None,
        is_resident=resident,
        docNumber=_text(record.get("docNumber")) or None,
        docBegin=_date(record, "docBegin"),
        docEnd=doc_end,
        docIssue=_text(record.get("docIssue")),
        sexId=_text(record.get("sexId")),
        dateAdd=_moment(record, "dateAdd"),
        visitObjects=_text(record.get("visitObjects")),
        transcription=_text(record.get("transcription")),
        dateEnd=doc_end,
        stickId=_text(record.get("stickId"))[:20],
    )


def _open_request(event, operator):
    """Открытая заявка импорта: последняя Active того же оператора за час, иначе новая.

    Отправленные и выгруженные заявки не пополняются.
    """
    now = timezone.now()
    current = (
        Request.objects.filter(event=event, created_by=operator, status="Active",
                               registration_time__gte=now - timedelta(hours=1))
        .order_by("-registration_time")
        .first()
    )
    if current:
        return current
    return Request.objects.create(
        name=now.strftime("%Y%m%d%H%M%S"), event=event, status="Active",
        created_by=operator, registration_time=now,
    )


def _store(source, event, key, outcome, payload, attendee=None):
    try:
        with transaction.atomic():
            return PartnerReceipt.objects.create(
                source=source.name, event=event, external_id=key,
                outcome=outcome, ack_payload=payload, attendee=attendee,
            )
    except IntegrityError:
        # Параллельный запуск уже записал эту анкету.
        return PartnerReceipt.objects.get(source=source.name, event=event, external_id=key)


def receive(source, event, operator, record):
    """Обрабатывает одну анкету. ``None`` — у анкеты нет идентификатора."""
    key = _external_key(record)
    if key is None:
        return None
    raw_id = record.get("id")
    lookup = dict(source=source.name, event=event, external_id=key)

    known = PartnerReceipt.objects.filter(**lookup).first()
    if known:
        return known

    try:
        with intake.event_intake(event.pk):
            known = PartnerReceipt.objects.filter(**lookup).first()
            if known:
                return known

            missing = [name for name in source.required if _empty(record.get(name))]
            if missing:
                return _store(source, event, key, PartnerReceipt.REJECTED, source.missing_ack(raw_id, missing))

            attendee = _build_attendee(record)
            if intake.duplicate_of(attendee, event.pk):
                return _store(source, event, key, PartnerReceipt.DUPLICATE, source.duplicate_ack(raw_id))

            notes = []
            for name in intake.MEDIA_FIELDS:
                stored, reason = intake.decode_partner_file(name, record.get(name), intake.random_stem(name))
                if stored is not None:
                    setattr(attendee, name, stored)
                elif reason:
                    notes.append(f"{_FILE_LABEL[name]} не принято: {reason[:1].lower() + reason[1:]}")

            attendee.request = _open_request(event, operator)
            intake.save_with_file_cleanup(attendee)
            return _store(
                source, event, key, PartnerReceipt.ACCEPTED,
                source.success_ack(raw_id, attendee, notes), attendee,
            )
    except RecordError as exc:
        return _store(source, event, key, PartnerReceipt.REJECTED, source.failure_ack(raw_id, str(exc)))
    except Exception:  # noqa: BLE001 — ошибка записи: партнёр получает отказ, данные в журнал не попадают
        logger.error("Partner record could not be saved")
        return _store(
            source, event, key, PartnerReceipt.REJECTED,
            source.failure_ack(raw_id, "Participant could not be saved"),
        )


def mark_ack(receipt_pk, status):
    receipt = PartnerReceipt.objects.get(pk=receipt_pk)
    receipt.ack_attempts += 1
    receipt.last_ack_status = status
    if 200 <= status < 300:
        receipt.acked_at = timezone.now()
    receipt.save(update_fields=["ack_attempts", "last_ack_status", "acked_at"])


@dataclass
class ImportResult:
    processed: int = 0
    accepted: int = 0
    duplicates: int = 0
    errors: int = 0
    request_id: int | None = None
    upstream_failed: bool = False
    seen: set = field(default_factory=set)

    def payload(self):
        return {
            "processed": self.processed, "accepted": self.accepted, "duplicates": self.duplicates,
            "errors": self.errors, "request_id": self.request_id,
        }


async def run(source, event, operator, client, *, get_url, ack_url, headers_get, headers_post,
              stop_statuses=(), pause=0.0):
    """Забирает анкеты по одной, пока очередь не опустеет или не сработает предохранитель."""
    result = ImportResult()
    limit = getattr(settings, "PARTNER_IMPORT_MAX_RECORDS", 500)
    for _ in range(limit):
        try:
            response = await client.get(get_url, headers=headers_get)
        except Exception:  # noqa: BLE001
            logger.error("Partner queue request failed")
            result.upstream_failed = True
            break
        if response.status_code in stop_statuses:
            break
        if response.status_code != 200:
            logger.error("Partner queue response status=%d", response.status_code)
            result.upstream_failed = True
            break
        try:
            body = response.json()
            items = (body.get("attendees") or []) if isinstance(body, dict) else []
        except ValueError:
            result.upstream_failed = True
            break
        if not items:
            break
        record = items[0]
        receipt = await sync_to_async(receive)(source, event, operator, record) if isinstance(record, dict) else None
        if receipt is None:
            # Без идентификатора подтвердить нельзя: партнёр вернёт ту же анкету.
            logger.error("Partner record without identifier; import stopped")
            result.errors += 1
            break
        result.processed += 1
        if receipt.pk in result.seen:
            logger.warning("Partner returned an acknowledged record again; import stopped")
            break
        result.seen.add(receipt.pk)
        if receipt.outcome == PartnerReceipt.ACCEPTED:
            result.accepted += 1
            if receipt.attendee_id:
                result.request_id = await sync_to_async(
                    lambda: Attendee.objects.filter(pk=receipt.attendee_id).values_list("request_id", flat=True).first()
                )()
        elif receipt.outcome == PartnerReceipt.DUPLICATE:
            result.duplicates += 1
        else:
            result.errors += 1

        try:
            ack = await client.post(ack_url, headers=headers_post, json=receipt.ack_payload)
            status = ack.status_code
        except Exception:  # noqa: BLE001
            status = 0
        logger.info("Partner acknowledgement status=%d", status)
        await sync_to_async(mark_ack)(receipt.pk, status)
        if not 200 <= status < 300:
            # Остановка: при следующем запуске та же анкета получит то же подтверждение.
            result.errors += 1
            break
        if pause:
            await asyncio.sleep(pause)
    return result
