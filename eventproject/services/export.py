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
  атрибуты элементов. Манифест хранит SHA-256, размер и CRC-32 каждого элемента.
- Архив не собирается на диске и не хранится: `services/zipstream.py` складывает
  его прямо в ответ (без сжатия — JPEG не сжимается), поэтому размер известен
  заранее, память не зависит от объёма, а повторная выдача умеет докачку (Range).
- iin — EncryptedCharField: расшифровывается при доступе; в экспорт идёт только для резидента.
- Справочники: countryId=Country.country_code, sexId=Sex.sex_code, docTypeId=DocumentType.doc_code.
"""

import hashlib
import json
import os
import zlib
from datetime import datetime
from datetime import timezone as dt_timezone

from django.utils import timezone

from directories.models import Country, DocumentType, Sex
from eventproject.models import Attendee, ExportLog
from eventproject.services import zipstream
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


SCHEMA_VERSION = "1.1"


def build_export_object(attendee, dir_names=None):
    """Объект attendee по Integration Spec v1.1 (единый источник формата).

    hd-1.1: bump 1.0→1.1 — аддитивное поле `schema_version` (см.
    docs/integration-spec-v1.md «Политика версионирования»); resident-ИИН НЕ
    трогается (подтверждено Erda 2026-06-23, story hd-1.1 Dev Notes).
    """
    if dir_names is None:
        dir_names = load_directory_names()
    return {
        "attendee_id": attendee.id,
        "schema_version": SCHEMA_VERSION,
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


ExportSourceChanged = zipstream.SourceChanged


class PackageMismatch(Exception):
    """Состав или данные пакета разошлись с манифестом. `args[0]` — имена элементов."""


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


def _media_entries(attendee, obj):
    """(имя в архиве, путь к файлу) медиа участника в порядке архива."""
    for key, filefield in (("photo_file", attendee.photo), ("doc_scan_file", attendee.docScan)):
        arcname = obj[key]
        if arcname is not None:
            yield arcname, _media_path(filefield)


def describe_package(pairs):
    """Манифест нового пакета: {имя: {sha256, size, crc32}} и отпечатки файлов.

    Файлы читаются один раз блоками. Отпечаток (размер, mtime_ns) позволяет под
    блокировкой дёшево убедиться, что файл не заменили после подсчёта. Пропавший
    файл → ExportSourceChanged.
    """
    manifest = {}
    stamps = {}
    for attendee, obj in pairs:
        for arcname, path in _media_entries(attendee, obj):
            if path is None:
                raise ExportSourceChanged(arcname)
            try:
                before = os.stat(path)
                size, crc, sha = zipstream.describe_file(path)
            except OSError as exc:
                raise ExportSourceChanged(arcname) from exc
            manifest[arcname] = {"sha256": sha, "size": size, "crc32": crc}
            stamps[arcname] = (path, before.st_size, before.st_mtime_ns)
    data = attendees_json_bytes([obj for _, obj in pairs])
    manifest["attendees.json"] = {"sha256": sha256_hex(data), "size": len(data), "crc32": zlib.crc32(data)}
    return manifest, stamps


def files_unchanged(stamps):
    """True, если файлы пакета не менялись с момента `describe_package`."""
    for path, size, mtime_ns in stamps.values():
        try:
            current = os.stat(path)
        except OSError:
            return False
        if (current.st_size, current.st_mtime_ns) != (size, mtime_ns):
            return False
    return True


def is_stream_manifest(manifest):
    """Манифест потокового пакета ({имя: {sha256, size, crc32}})."""
    return bool(manifest) and all(isinstance(value, dict) for value in manifest.values())


def package_stream(pairs, manifest, packaged_at):
    """ZipStream пакета: элементы в порядке участников, затем attendees.json.

    Ожидаемые размер, CRC и SHA-256 каждого элемента берутся из манифеста; при
    отдаче файл сверяется с ними (расхождение обрывает поток). Расхождение,
    видимое заранее (другой состав, нет файла, другой размер, другой JSON), —
    PackageMismatch со списком имён.
    """
    entries = []
    differences = []
    names = []
    for attendee, obj in pairs:
        for arcname, path in _media_entries(attendee, obj):
            names.append(arcname)
            expected = manifest.get(arcname)
            if expected is None or path is None:
                differences.append(arcname)
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                differences.append(arcname)
                continue
            if size != expected["size"]:
                differences.append(arcname)
                continue
            entries.append(zipstream.Entry(
                arcname, expected["size"], expected["crc32"], expected["sha256"], path=path,
            ))
    data = attendees_json_bytes([obj for _, obj in pairs])
    names.append("attendees.json")
    expected = manifest.get("attendees.json") or {}
    if sha256_hex(data) != expected.get("sha256"):
        differences.append("attendees.json")
    else:
        entries.append(zipstream.Entry("attendees.json", len(data), zlib.crc32(data), expected["sha256"], data=data))
    differences += sorted(set(manifest) - set(names))
    if differences:
        raise PackageMismatch(differences)
    date_time = packaged_at.astimezone(dt_timezone.utc).timetuple()[:6]
    return zipstream.ZipStream(entries, date_time)


def stream_sha256(stream):
    """SHA-256 всего архива: один проход по потоку, без записи на диск."""
    digest = hashlib.sha256()
    for chunk in stream.iter_bytes():
        digest.update(chunk)
    return digest.hexdigest()
