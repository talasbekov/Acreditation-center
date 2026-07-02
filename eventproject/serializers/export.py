"""Story hd-1.1 — whitelist-сериализатор для легаси JSON-экспорта (file_download.py).

Гэп (docs/accreditation-gap-analysis.md §3.1): `eventproject/views/file_download.py`
строил JSON через `model_to_dict()` — дамп ВСЕХ полей модели (расшифрованный ИИН,
служебные review-workflow поля `problem_flags`/`last_return_reason`/`return_count`,
`stickId`). Этот модуль — явный whitelist, независимый от
`eventproject/services/export.py::build_export_object` (Integration Spec v1.0,
resident-ИИН для downstream службы охраны, подтверждено Erda 2026-06-23) — тот путь
НЕ трогается этой историей, см. story hd-1.1 Dev Notes «Премиса-конфликт».

`LEGACY_ATTENDEE_FIELDS`/`LEGACY_EVENT_FIELDS` — единственный источник правды
набора полей: билдеры перечисляют ключи явно (не `**vars()`), тест
`test_export_whitelist.py` проверяет set-equality — новое поле модели не может
протечь в выгрузку молча.

Легаси-эндпоинты отдают чистый JSON (без ZIP-архива) — в отличие от
`services/export.py`, media отдаются как защищённый URL (`photo_url`/`doc_scan_url`,
паттерн `serializers/review_queue.py::_media_url`), не как arcname-путь в
несуществующем архиве.
"""

from eventproject.services.export import _fmt_date, _fmt_datetime, load_directory_names

LEGACY_SCHEMA_VERSION = "legacy-1"

LEGACY_ATTENDEE_FIELDS = frozenset(
    {
        "attendee_id",
        "event_id",
        "category",
        "status",
        "surname",
        "firstname",
        "patronymic",
        "transcription",
        "birth_date",
        "is_resident",
        "sex_id",
        "sex_name",
        "country_id",
        "country_name",
        "post",
        "doc_type_id",
        "doc_type_name",
        "doc_series",
        "doc_number",
        "doc_begin",
        "doc_end",
        "doc_issue",
        "visit_objects",
        "date_add",
        "photo_url",
        "doc_scan_url",
        "schema_version",
    }
)

LEGACY_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "event_code",
        "name_rus",
        "name_kaz",
        "name_eng",
        "date_start",
        "date_end",
        "city_code",
        "schema_version",
    }
)

LEGACY_REQUEST_FIELDS = frozenset(
    {
        "request_id",
        "name",
        "event_id",
        "status",
        "date_created",
        "created_by_id",
        "exported_by_id",
        "schema_version",
    }
)


def _media_url(file_field, request=None):
    """Защищённый URL медиа или None (mirror serializers/review_queue.py::_media_url).

    Пустой ImageField → None (не битая ссылка). Дополнительно (в отличие от
    review_queue.py — там read-API, здесь скачиваемый JSON-артефакт): проверяем
    наличие файла на диске, mirror `services/export.py::_add_media` (review 4.3,
    D5) — отсутствующий на диске файл → None, а не битая ссылка в выгрузку.
    `.url`/`.storage.exists()` могут бросать не только ValueError (напр.
    NotImplementedError на storage-бэкендах без URL) — ловим оба, чтобы одно
    плохое медиа-поле не 500-ило и не откатывало весь atomic-блок экспорта.
    С `request` — абсолютный URL (protected /media/ под session-cookie); без —
    относительный (детерминирован для тестов/фикстур).
    """
    if not file_field or not file_field.name:
        return None
    try:
        if not file_field.storage.exists(file_field.name):
            return None
        url = file_field.url
    except (ValueError, NotImplementedError):
        return None
    return request.build_absolute_uri(url) if request is not None else url


def build_legacy_attendee_dict(attendee, dir_names=None, request=None):
    """Whitelist-объект участника для легаси JSON-экспорта. БЕЗ `iin` и служебных полей."""
    if dir_names is None:
        dir_names = load_directory_names()
    return {
        "attendee_id": attendee.id,
        "event_id": attendee.request.event_id,
        "category": attendee.category.name if attendee.category_id else None,
        "status": attendee.status,
        "surname": attendee.surname,
        "firstname": attendee.firstname,
        "patronymic": attendee.patronymic or None,
        "transcription": attendee.transcription,
        "birth_date": _fmt_date(attendee.birthDate),
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
        "photo_url": _media_url(attendee.photo, request),
        "doc_scan_url": _media_url(attendee.docScan, request),
        "schema_version": LEGACY_SCHEMA_VERSION,
    }


def build_legacy_event_dict(event):
    """Whitelist-объект мероприятия для легаси JSON-экспорта.

    `Event` хранит 2 параллельных набора полей: legacy (`name_rus`/`date_start`/
    `event_code`/`city_code`) и Story 2.2 REST (`title`/`start_date`/`end_date`,
    `serializers/event.py::EventSerializer`). Событие, созданное через REST API,
    пишет ТОЛЬКО новые поля — legacy остаются NULL. Coalesce на новые, иначе
    экспорт такого события уходит с пустой шапкой (review hd-1.1, Edge Case
    Hunter) — `model_to_dict` раньше показывал оба набора, whitelist иначе терял
    бы видимость в один из них. `event_code`/`city_code` REST-эквивалента не
    имеют (нет в `EventSerializer.Meta.fields`) — остаются null для таких событий;
    это гэп самой Story 2.2, не в скоупе hd-1.1.
    """
    return {
        "event_id": event.id,
        "event_code": event.event_code,
        "name_rus": event.name_rus or event.title,
        "name_kaz": event.name_kaz or event.title,
        "name_eng": event.name_eng or event.title,
        "date_start": _fmt_date(event.date_start or event.start_date),
        "date_end": _fmt_date(event.date_end or event.end_date),
        "city_code": event.city_code,
        "schema_version": LEGACY_SCHEMA_VERSION,
    }


def build_legacy_request_dict(req):
    """Whitelist-объект категории-заявки (Request) для легаси JSON-экспорта.

    FK (`created_by`/`exported_by`) — сырой id (как отдавал `model_to_dict`), не
    вложенный Operator-объект: имя/телефон оператора здесь не нужны и не отдаются.
    """
    return {
        "request_id": req.id,
        "name": req.name,
        "event_id": req.event_id,
        "status": req.status,
        "date_created": _fmt_datetime(req.date_created),
        "created_by_id": req.created_by_id,
        "exported_by_id": req.exported_by_id,
        "schema_version": LEGACY_SCHEMA_VERSION,
    }
