"""Story 4.3 — delta-export участников в downstream security-систему.

Единый источник формата — docs/integration-spec-v1.md (v1.0) и его машиночитаемый
контракт docs/integration-spec-v1.schema.json. `build_export_object` строит ровно те
поля и форматы; contract-тест (test_export_contract / test_export_delta) проверяет
соответствие. Strangler Fig: новый модуль, legacy download_json не трогаем.

Ключевые нюансы:
- «Категория» экспорта = `Request` (ExportLog.category — FK на Request, не Category).
- Состав пакета (этап C): все `ready`-участники категории. Граница по dateAdd не
  используется: карточка, созданная раньше прошлой выгрузки и одобренная позже,
  попадает в следующую. Повтор исключён терминальным переходом ready → exported.
- Архив детерминирован: фиксированные метка времени (момент пакета), порядок и
  атрибуты элементов. Манифест хранит SHA-256 каждого элемента для повторной выдачи.
- iin — EncryptedCharField: расшифровывается при доступе; в экспорт идёт только для резидента.
- Справочники: countryId=Country.country_code, sexId=Sex.sex_code, docTypeId=DocumentType.doc_code.
"""

import hashlib
import json
import os
import zipfile
from datetime import datetime
from datetime import timezone as dt_timezone

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


class ExportSourceChanged(Exception):
    """Файл участника исчез между подготовкой пакета и записью архива."""


def select_ready_attendees(request_obj):
    """Все `ready`-участники категории в порядке id — состав следующего пакета."""
    return (
        Attendee.objects.filter(request=request_obj, status=AttendeeStatus.READY)
        .select_related("request__event", "category")
        .order_by("id")
    )


def _media_path(filefield):
    """Путь к существующему файлу участника или None (пустая ссылка / нет на диске)."""
    if not (filefield and filefield.name):
        return None
    try:
        path = filefield.path
    except (ValueError, NotImplementedError):
        return None
    return path if os.path.exists(path) else None


def prepare_package_objects(attendees, dir_names=None):
    """Пары (attendee, объект Spec v1.0) в порядке пакета.

    Ссылки photo_file/doc_scan_file сразу синхронизируются с наличием файла на
    диске: нет файла → null (ревью 4.3, D5; не битая ссылка). `status` фиксируется
    как `ready` — пакет описывает участника в момент выгрузки, и при повторной
    выдаче уже выгруженного участника содержимое не должно меняться.
    """
    if dir_names is None:
        dir_names = load_directory_names()
    pairs = []
    for attendee in attendees:
        obj = build_export_object(attendee, dir_names)
        obj["status"] = AttendeeStatus.READY
        if _media_path(attendee.photo) is None:
            obj["photo_file"] = None
        if _media_path(attendee.docScan) is None:
            obj["doc_scan_file"] = None
        pairs.append((attendee, obj))
    return pairs


def attendees_json_bytes(objects):
    return json.dumps(objects, ensure_ascii=False, indent=2).encode("utf-8")


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def write_package(fileobj, pairs, packaged_at):
    """Записать детерминированный ZIP пакета и вернуть манифест {имя: SHA-256}.

    Состав: photos/<id>.<ext> и documents/<id>.<ext> в порядке участников, затем
    attendees.json. Метка времени всех элементов — `packaged_at` в UTC, атрибуты
    не зависят от ОС и mtime файлов, поэтому та же исходная информация даёт тот же
    архив. Если упомянутый в JSON файл пропал — ExportSourceChanged.
    """
    date_time = packaged_at.astimezone(dt_timezone.utc).timetuple()[:6]
    manifest = {}

    with zipfile.ZipFile(fileobj, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zipf:
        def put(name, data):
            info = zipfile.ZipInfo(name, date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            zipf.writestr(info, data, compresslevel=1)
            manifest[name] = sha256_hex(data)

        for attendee, obj in pairs:
            for key, filefield in (("photo_file", attendee.photo), ("doc_scan_file", attendee.docScan)):
                arcname = obj[key]
                if arcname is None:
                    continue
                path = _media_path(filefield)
                if path is None:
                    raise ExportSourceChanged(arcname)
                with open(path, "rb") as source:
                    put(arcname, source.read())
        put("attendees.json", attendees_json_bytes([obj for _, obj in pairs]))
    return manifest


def file_sha256(fileobj):
    """SHA-256 содержимого файла; позиция возвращается в начало."""
    fileobj.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: fileobj.read(1024 * 1024), b""):
        digest.update(chunk)
    fileobj.seek(0)
    return digest.hexdigest()


def manifest_differences(expected, actual):
    """Имена элементов, которые отсутствуют, добавились или изменились."""
    names = set(expected or {}) | set(actual or {})
    return sorted(n for n in names if (expected or {}).get(n) != (actual or {}).get(n))
