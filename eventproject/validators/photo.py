"""Story 5.3 — валидация изображения (фото участника и скан документа).

Единый источник правды проверок изображения: размер ≤ 5 МБ, целостность,
лимит пикселей (анти-decompression-bomb), вертикальная ориентация (ratio
ширина/высота ≤ 0.85 — формат 3×4), разрешение ≥ 600×800. Переиспользуется и
для `photo`, и для `docScan` (последний — после PDF→JPEG).

`docScan` принимает PDF: `is_pdf` детектит по сигнатуре `%PDF-`, `convert_pdf_to_jpeg`
рендерит первую страницу в JPEG (pdf2image + poppler-utils, bounded dpi), далее
результат проходит ту же `validate_image_file`, что и фото (решение Erda 2026-06-24).
"""

from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

# Дословные сообщения (AC-3). Тесты и фронтенд опираются на эти строки.
ERR_TOO_BIG = "Файл слишком большой (максимум 5 МБ)"
ERR_NOT_VERTICAL = "Фото должно быть вертикальным (формат 3×4)"
ERR_LOW_RES = "Разрешение слишком низкое (минимум 600×800 пикселей)"
ERR_NOT_IMAGE = "Файл не является изображением"
ERR_TOO_MANY_PIXELS = "Изображение слишком большое (превышен лимит пикселей)"
ERR_PDF_FAILED = "Не удалось обработать PDF-документ"


def _limits():
    """Лимиты из settings (override_settings-friendly)."""
    return (
        getattr(settings, "PHOTO_MAX_SIZE_BYTES", 5 * 1024 * 1024),
        getattr(settings, "PHOTO_MAX_RATIO", 0.85),
        getattr(settings, "PHOTO_MIN_WIDTH", 600),
        getattr(settings, "PHOTO_MIN_HEIGHT", 800),
        getattr(settings, "PHOTO_MAX_PIXELS", 40_000_000),  # ~40 МП анти-bomb
    )


def check_upload_size(file):
    """Размер ≤ PHOTO_MAX_SIZE_BYTES на ИСХОДНОМ загруженном файле (AC-3).

    Отдельно — чтобы для PDF проверить размер ДО конвертации (иначе лимит мерялся
    бы на сконвертированном JPEG, а не на исходнике).
    """
    max_size = getattr(settings, "PHOTO_MAX_SIZE_BYTES", 5 * 1024 * 1024)
    size = getattr(file, "size", None)
    if size is not None and size > max_size:
        raise serializers.ValidationError(ERR_TOO_BIG)


def validate_image_file(file):
    """Проверяет загруженный файл-изображение. Бросает ``serializers.ValidationError``.

    Порядок (AC-3): размер → лимит пикселей (до декода) → целостность → вертикальность
    → разрешение. Лимит пикселей и `img.load()` защищают от decompression-bomb и
    усечённых/битых файлов (раньше проходили — только `.size` читался из заголовка).
    """
    max_size, max_ratio, min_w, min_h, max_pixels = _limits()

    check_upload_size(file)

    try:
        file.seek(0)
        with Image.open(file) as img:
            width, height = img.size
            # Лимит пикселей — ДО декодирования (анти-bomb: 600×200000 и т.п.).
            if width * height > max_pixels:
                raise serializers.ValidationError(ERR_TOO_MANY_PIXELS)
            img.load()  # форсируем декод → ловим усечённые/битые изображения
    except serializers.ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise serializers.ValidationError(ERR_NOT_IMAGE)
    finally:
        try:
            file.seek(0)
        except (OSError, ValueError):
            pass

    if height <= 0 or width / height > max_ratio:
        raise serializers.ValidationError(ERR_NOT_VERTICAL)
    if width < min_w or height < min_h:
        raise serializers.ValidationError(ERR_LOW_RES)


def is_pdf(uploaded):
    """PDF определяется по сигнатуре ``%PDF-`` (надёжно), content_type — резерв."""
    try:
        uploaded.seek(0)
        head = uploaded.read(5)
        uploaded.seek(0)
    except (OSError, ValueError):
        head = b""
    if head[:5] == b"%PDF-":
        return True
    content_type = (getattr(uploaded, "content_type", "") or "").lower()
    return content_type == "application/pdf"


def convert_pdf_to_jpeg(uploaded):
    """PDF (UploadedFile) → JPEG ``ContentFile`` первой страницы. Story 5.3 AC-4.

    Требует системный poppler-utils (Dockerfile). Рендер ограничен `PDF_RENDER_DPI`
    и лимитом пикселей (анти-bomb); ЛЮБАЯ ошибка рендера/декода → понятное 400
    (`ERR_PDF_FAILED`), не 500. Имя — basename + ``.jpg``.
    """
    from pdf2image import convert_from_bytes

    max_pixels = getattr(settings, "PHOTO_MAX_PIXELS", 40_000_000)
    dpi = getattr(settings, "PDF_RENDER_DPI", 150)
    try:
        uploaded.seek(0)
        data = uploaded.read()
        pages = convert_from_bytes(data, first_page=1, last_page=1, fmt="jpeg", dpi=dpi)
        if not pages:
            raise serializers.ValidationError(ERR_PDF_FAILED)
        page = pages[0]
        # Анти-bomb: не декодируем гигантскую страницу в RGB.
        if page.width * page.height > max_pixels:
            raise serializers.ValidationError(ERR_PDF_FAILED)
        buf = BytesIO()
        page.convert("RGB").save(buf, format="JPEG", quality=85)
    except serializers.ValidationError:
        raise
    except Exception:  # noqa: BLE001 — poppler/Pillow/bomb → понятное 400, не 500
        raise serializers.ValidationError(ERR_PDF_FAILED)
    finally:
        try:
            uploaded.seek(0)
        except (OSError, ValueError):
            pass

    base = (getattr(uploaded, "name", None) or "document").rsplit(".", 1)[0]
    return ContentFile(buf.getvalue(), name=f"{base}.jpg")
