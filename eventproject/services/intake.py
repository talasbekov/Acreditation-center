"""Этап C — единый приём участника для всех путей ввода.

HTML RU/KZ/EN, DRF API и импорт партнёров используют одно правило дублей,
одну проверку вложений и одну блокировку мероприятия на время «проверить и
записать».

Правило дублей (решение владельца 25.11.2026) в пределах мероприятия:
- резидент РК — тот же ИИН;
- нерезидент — то же гражданство, тип, серия и номер документа (без учёта
  регистра, пробелов и дефисов). Однофамильцы с разными документами не
  сливаются. Без номера документа нерезидент дублем не считается.
"""

import base64
import binascii
import uuid
from contextlib import contextmanager

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image
from rest_framework import serializers

from eventproject.models import Attendee, Event
from eventproject.validators import photo as photo_rules
from eventproject.validators.iin import event_has_iin_duplicate
from eventproject.validators.residency import is_resident_country

MEDIA_FIELDS = ("photo", "docScan")

_DUPLICATE_TEXT = {
    "ru": {
        "iin": "Участник с этим ИИН уже добавлен в это мероприятие.",
        "document": "Участник с этим документом уже добавлен в это мероприятие.",
    },
    "kz": {
        "iin": "Осы ЖСН-мен қатысушы бұл іс-шараға бұрын қосылған.",
        "document": "Осы құжатпен қатысушы бұл іс-шараға бұрын қосылған.",
    },
    "en": {
        "iin": "An attendee with this IIN has already been added to this event.",
        "document": "An attendee with this document has already been added to this event.",
    },
}

_FIELD_LABEL = {
    "ru": {"photo": "Фото", "docScan": "Скан документа"},
    "kz": {"photo": "Сурет", "docScan": "Құжат көшірмесі"},
    "en": {"photo": "Photo", "docScan": "Document scan"},
}

# Тексты правил вложений: русский — из validators/photo.py (на них опираются
# API и фронтенд), казахский и английский — для HTML-форм.
_UPLOAD_TEXT = {
    photo_rules.ERR_TOO_BIG: {
        "kz": "файл тым үлкен (ең көбі 5 МБ)",
        "en": "the file is too large (5 MB maximum)",
    },
    photo_rules.ERR_NOT_VERTICAL: {
        "kz": "сурет тік болуы керек (3×4 форматы)",
        "en": "the image must be vertical (3×4 format)",
    },
    photo_rules.ERR_LOW_RES: {
        "kz": "ажыратымдылығы тым төмен (кемінде 600×800 пиксель)",
        "en": "the resolution is too low (at least 600×800 pixels)",
    },
    photo_rules.ERR_NOT_IMAGE: {
        "kz": "файл JPEG, PNG немесе WEBP суреті емес",
        "en": "the file is not a JPEG, PNG or WEBP image",
    },
    photo_rules.ERR_TOO_MANY_PIXELS: {
        "kz": "сурет тым үлкен (пиксель шегінен асады)",
        "en": "the image is too large (pixel limit exceeded)",
    },
    photo_rules.ERR_PDF_FAILED: {
        "kz": "PDF құжатын өңдеу мүмкін болмады",
        "en": "the PDF document could not be processed",
    },
    photo_rules.ERR_MISSING: {
        "kz": "файл жүктелмеді",
        "en": "no file was uploaded",
    },
}

_PIL_EXTENSION = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class UploadRejected(Exception):
    """Вложение не прошло правила. ``message`` — русский текст из photo.py."""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field
        self.message = message


# ── Дубли ────────────────────────────────────────────────────────────────


def _norm(value):
    return "".join(str(value or "").split()).replace("-", "").upper()


def find_duplicate(event_id, *, country_id, iin, doc_type, doc_series, doc_number, exclude_pk=None):
    """Возвращает ``"iin"``, ``"document"`` или ``None``."""
    existing = Attendee.objects.filter(request__event_id=event_id)
    if exclude_pk is not None:
        existing = existing.exclude(pk=exclude_pk)

    if is_resident_country(country_id):
        return "iin" if event_has_iin_duplicate(existing, iin) else None

    number = _norm(doc_number)
    if not number:
        return None
    series = _norm(doc_series)
    candidates = existing.filter(
        countryId=str(country_id or "").strip(),
        docTypeId=str(doc_type or "").strip(),
    ).values_list("docSeries", "docNumber")
    for other_series, other_number in candidates:
        if _norm(other_number) == number and _norm(other_series) == series:
            return "document"
    return None


def duplicate_of(attendee, event_id):
    return find_duplicate(
        event_id,
        country_id=attendee.countryId,
        iin=attendee.iin,
        doc_type=attendee.docTypeId,
        doc_series=attendee.docSeries,
        doc_number=attendee.docNumber,
        exclude_pk=attendee.pk,
    )


def duplicate_text(code, lang="ru"):
    return _DUPLICATE_TEXT.get(lang, _DUPLICATE_TEXT["ru"])[code]


@contextmanager
def event_intake(event_id):
    """Транзакция с блокировкой строки мероприятия.

    Два одновременных добавления в одно мероприятие проверяют дубли и пишут по
    очереди, поэтому двойное нажатие или параллельный импорт не создают двух
    одинаковых участников. В SQLite запись сериализуется самой базой.
    """
    with transaction.atomic():
        list(Event.objects.select_for_update().filter(pk=event_id).values_list("pk", flat=True))
        yield


def save_unless_duplicate(attendee, event_id):
    """Проверяет дубль и сохраняет участника под блокировкой мероприятия.

    Возвращает код дубля (и ничего не пишет) либо ``None`` после записи. Если
    запись в БД не удалась, уже сохранённые в хранилище файлы удаляются.
    """
    with event_intake(event_id):
        code = duplicate_of(attendee, event_id)
        if code:
            return code
        save_with_file_cleanup(attendee)
    return None


def save_with_file_cleanup(attendee):
    # Этап E: при правке существующего участника его прежние файлы уже принадлежат
    # сохранённой записи — при сбое записи их удалять нельзя (раньше неудачная правка,
    # например с пустой датой, стирала с диска фото и скан участника).
    keep = set()
    if attendee.pk:
        stored = type(attendee).objects.filter(pk=attendee.pk).values_list(*MEDIA_FIELDS).first()
        keep = {name for name in (stored or ()) if name}
    try:
        attendee.save()
    except Exception:
        discard_stored_files(attendee, keep=keep)
        raise


def discard_stored_files(attendee, keep=()):
    """Удаляет из хранилища файлы несохранённой записи (иначе остаются сироты).

    ``keep`` — имена файлов, на которые уже ссылается сохранённая запись: их не трогаем.
    """
    for field in MEDIA_FIELDS:
        file = getattr(attendee, field, None)
        if file and getattr(file, "_committed", False) and file.name and file.name not in keep:
            try:
                file.storage.delete(file.name)
            except OSError:
                pass


# ── Вложения ─────────────────────────────────────────────────────────────


def _first_message(exc):
    detail = exc.detail
    if isinstance(detail, (list, tuple)) and detail:
        return str(detail[0])
    return str(detail)


def clean_upload(field, uploaded):
    """Проверяет фото или скан по правилам API. PDF скана → JPEG первой страницы.

    Возвращает файл для записи (для PDF — сконвертированный), иначе
    ``UploadRejected``.
    """
    if not uploaded:
        raise UploadRejected(field, photo_rules.ERR_MISSING)
    try:
        if field == "docScan" and photo_rules.is_pdf(uploaded):
            photo_rules.check_upload_size(uploaded)
            uploaded = photo_rules.convert_pdf_to_jpeg(uploaded)
        photo_rules.validate_image_file(uploaded)
    except serializers.ValidationError as exc:
        raise UploadRejected(field, _first_message(exc))
    return uploaded


def upload_text(exc, lang="ru"):
    label = _FIELD_LABEL.get(lang, _FIELD_LABEL["ru"])[exc.field]
    if lang == "ru":
        reason = exc.message[:1].lower() + exc.message[1:]
    else:
        reason = _UPLOAD_TEXT.get(exc.message, {}).get(lang, exc.message)
    return f"{label}: {reason}"


def apply_uploads(attendee, files, lang="ru", required=True):
    """HTML-формы: проверяет и подставляет ``photo``/``doc_photo``.

    Возвращает текст ошибки на языке формы либо пустую строку. При
    ``required=False`` (правка) отсутствующий файл оставляет прежний.
    """
    for field, form_name in (("photo", "photo"), ("docScan", "doc_photo")):
        uploaded = files.get(form_name)
        if not uploaded and not required:
            continue
        try:
            setattr(attendee, field, clean_upload(field, uploaded))
        except UploadRejected as exc:
            return upload_text(exc, lang)
    return ""


def decode_partner_file(field, value, stem):
    """Импорт: data URI / base64 → проверенный ``ContentFile`` либо причина отказа.

    Возвращает ``(file, "")`` или ``(None, причина)``. Размер ограничивается до
    декодирования. Имя файла случайное: идентификатор партнёра и ПД в путь не
    попадают.
    """
    if not value:
        return None, ""
    if not isinstance(value, str):
        return None, photo_rules.ERR_NOT_IMAGE
    payload = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    payload = "".join(payload.split())
    max_size = getattr(settings, "PHOTO_MAX_SIZE_BYTES", 5 * 1024 * 1024)
    if len(payload) * 3 // 4 > max_size + 3:
        return None, photo_rules.ERR_TOO_BIG
    payload += "=" * (-len(payload) % 4)
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None, photo_rules.ERR_NOT_IMAGE
    if not raw:
        return None, photo_rules.ERR_NOT_IMAGE
    try:
        cleaned = clean_upload(field, ContentFile(raw, name=f"{stem}.upload"))
    except UploadRejected as exc:
        return None, exc.message
    cleaned.seek(0)
    with Image.open(cleaned, formats=photo_rules.ALLOWED_IMAGE_FORMATS) as img:
        ext = _PIL_EXTENSION.get(img.format, "jpg")
    cleaned.seek(0)
    return ContentFile(cleaned.read(), name=f"{stem}.{ext}"), ""


def random_stem(field):
    return f"{uuid.uuid4().hex}_{field}"
