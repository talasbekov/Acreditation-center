"""Story 4.3 — delta-export участников в downstream security-систему.

Единый источник формата — docs/integration-spec-v1.md (v1.0) и его машиночитаемый
контракт docs/integration-spec-v1.schema.json. `build_export_object` строит ровно те
поля и форматы; contract-тест (test_export_contract / test_export_delta) проверяет
соответствие. Strangler Fig: новый модуль, legacy download_json не трогаем.

Ключевые нюансы:
- «Категория» экспорта = `Request` (ExportLog.category — FK на Request, не Category).
- Delta-граница: dateAdd > last_export.exported_before (строго) И dateAdd <= now (без gap).
- iin — EncryptedCharField: расшифровывается при доступе; в экспорт идёт только для резидента.
- Справочники: countryId=Country.country_code, sexId=Sex.sex_code, docTypeId=DocumentType.doc_code.
"""

import json
import os
import zipfile
from datetime import datetime

from django.utils import timezone

from directories.models import Country, DocumentType, Sex
from eventproject.models import Attendee, ExportLog
from eventproject.state_machine import AttendeeStatus

_DATE_FMT = "%d.%m.%Y"
_DATETIME_FMT = "%d.%m.%Y %H:%M:%S"


def load_directory_names():
    """code → name_rus по справочникам (одна выборка на справочник, не N+1)."""
    return {
        "country": {c.country_code: c.name_rus for c in Country.objects.all()},
        "sex": {s.sex_code: s.name_rus for s in Sex.objects.all()},
        "doc_type": {d.doc_code: d.name_rus for d in DocumentType.objects.all()},
    }


def _fmt_date(value):
    if not value:
        return None
    if isinstance(value, str):
        # ISO-строка из формы/БД до приведения типа → распарсить; иначе отдать как есть.
        try:
            value = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return value
    return value.strftime(_DATE_FMT)


def _fmt_datetime(value):
    if not value:
        return None
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime(_DATETIME_FMT)


def _media_arcname(folder, attendee, filefield):
    """Путь медиа в архиве или None, если файл к участнику не привязан."""
    if not (filefield and filefield.name):
        return None
    ext = os.path.splitext(filefield.name)[1]
    return f"{folder}/{attendee.id}{ext}"


def build_export_object(attendee, dir_names=None):
    """Объект attendee по Integration Spec v1.0 (единый источник формата)."""
    if dir_names is None:
        dir_names = load_directory_names()
    return {
        "attendee_id": attendee.id,
        "event_id": attendee.request.event_id,
        "event_code": attendee.request.event.event_code,
        # Attendee.category → eventproject.models.Category (поле `name`; name_rus НЕТ —
        # name_rus есть только у directories.Category). Ревью 4.3: фикс AttributeError.
        "category": attendee.category.name if attendee.category_id else None,
        "status": attendee.status,
        "surname": attendee.surname,
        "firstname": attendee.firstname,
        "patronymic": attendee.patronymic or None,
        "transcription": attendee.transcription,
        "birth_date": _fmt_date(attendee.birthDate),
        # ИИН — только для резидента (PII); нерезидент → null.
        "iin": attendee.iin if attendee.is_resident else None,
        "is_resident": attendee.is_resident,
        "sex_id": attendee.sexId,
        "sex_name": dir_names["sex"].get(attendee.sexId),
        "country_id": attendee.countryId,
        "country_name": dir_names["country"].get(attendee.countryId),
        "post": attendee.post,
        "doc_type_id": attendee.docTypeId,
        "doc_type_name": dir_names["doc_type"].get(attendee.docTypeId),
        "doc_series": attendee.docSeries,
        "doc_number": attendee.docNumber or None,
        "doc_begin": _fmt_date(attendee.docBegin),
        "doc_end": _fmt_date(attendee.docEnd),
        "doc_issue": attendee.docIssue,
        "visit_objects": attendee.visitObjects,
        "date_add": _fmt_datetime(attendee.dateAdd),
        "photo_file": _media_arcname("photos", attendee, attendee.photo),
        "doc_scan_file": _media_arcname("documents", attendee, attendee.docScan),
    }


def get_last_export(request_obj):
    """Последний ExportLog для этой категории (Request) или None (первый экспорт)."""
    return (
        ExportLog.objects.filter(category=request_obj)
        .order_by("-exported_before")
        .first()
    )


def select_new_attendees(request_obj, lower_boundary, upper_boundary):
    """`ready`-участники категории с dateAdd > lower_boundary и dateAdd <= upper_boundary.

    lower_boundary=None → первый экспорт (нижней границы нет). Граница строгая по
    нижнему краю (__gt: не включаем уже выгруженных) и нестрогая по верхнему
    (__lte=now: исключаем gap для записей, добавленных во время экспорта).
    """
    qs = Attendee.objects.filter(
        request=request_obj,
        status=AttendeeStatus.READY,
        dateAdd__lte=upper_boundary,
    )
    if lower_boundary is not None:
        qs = qs.filter(dateAdd__gt=lower_boundary)
    return qs.order_by("id")


def _add_media(zipf, filefield, arcname):
    """Добавляет файл в архив; возвращает arcname если добавлен, иначе None.

    None → файла нет на диске (или ссылка пустая): write_export_archive обнулит
    соответствующее поле в attendees.json, чтобы не было битой ссылки (ревью 4.3, D5).
    """
    if arcname is None or not (filefield and filefield.name):
        return None
    try:
        path = filefield.path
    except (ValueError, NotImplementedError):
        return None
    if not os.path.exists(path):
        return None
    zipf.write(path, arcname)
    return arcname


def write_export_archive(zip_path, attendees, objects):
    """Записать attendees.json + photos/<id>.<ext> + documents/<id>.<ext> в ZIP.

    Ссылки photo_file/doc_scan_file в JSON синхронизируются с фактическим наличием
    файла на диске: нет файла → поле = null (ревью 4.3, D5; не битая ссылка).
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zipf:
        for attendee, obj in zip(attendees, objects):
            obj["photo_file"] = _add_media(zipf, attendee.photo, obj["photo_file"])
            obj["doc_scan_file"] = _add_media(zipf, attendee.docScan, obj["doc_scan_file"])
        zipf.writestr(
            "attendees.json",
            json.dumps(objects, ensure_ascii=False, indent=2),
        )
