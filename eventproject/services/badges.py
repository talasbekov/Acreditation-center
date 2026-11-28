"""Бейджи участников (второй этап): отрисовка карточек и сборка PDF.

Карточка = фон мероприятия (или стандартный) + фото участника + ФИО. Разметка в
миллиметрах и долях карточки (`BadgeTemplate.layout`), по умолчанию — банковская
карта 85,6 × 54 мм при 300 DPI. PDF — по странице на бейдж, размер страницы равен
размеру карточки. Шрифт обязан знать казахские буквы (settings.BADGE_FONT_PATH).

Печатаются только участники с `access_status = "yes"` (бейдж — физический пропуск).
"""

import copy
import io
import logging
import os
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont, ImageOps

logger = logging.getLogger("eventproject")

MAX_BADGES_PER_JOB = 2000

DEFAULT_LAYOUT = {
    "badge": {"width_mm": 85.6, "height_mm": 54.0, "dpi": 300},
    # Окно фото: от левого верхнего угла, мм; скругление углов, мм.
    "photo": {"x_mm": 5.0, "y_mm": 13.0, "width_mm": 22.0, "height_mm": 29.0, "radius_mm": 2.0},
    # Окно ФИО: горизонтальные границы и верх — доли карточки; кегль в пунктах.
    "name": {"x0": 0.36, "x1": 0.96, "y": 0.36, "line_height": 0.13, "max_pt": 14, "min_pt": 7, "color": "#111827"},
}

FONT_CANDIDATES = [
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

# Казахские буквы, которые должен знать шрифт (проверяется при выборе шрифта).
KAZAKH_PROBE = "ӘҒҚҢӨҰҮҺәғқңөұүһ"


class BadgeError(Exception):
    pass


def merged_layout(layout):
    """Разметка шаблона поверх разметки по умолчанию (недостающие ключи — по умолчанию)."""
    out = copy.deepcopy(DEFAULT_LAYOUT)
    for section, values in (layout or {}).items():
        if section in out and isinstance(values, dict):
            for key, value in values.items():
                if key in out[section]:
                    out[section][key] = value
    return out


def validate_layout(layout):
    """Проверить разметку; вернуть полную разметку или BadgeError с текстом."""
    full = merged_layout(layout)
    b, p, n = full["badge"], full["photo"], full["name"]
    try:
        w, h, dpi = float(b["width_mm"]), float(b["height_mm"]), int(b["dpi"])
        px, py, pw, ph = (float(p[k]) for k in ("x_mm", "y_mm", "width_mm", "height_mm"))
        x0, x1, y, lh = (float(n[k]) for k in ("x0", "x1", "y", "line_height"))
        max_pt, min_pt = float(n["max_pt"]), float(n["min_pt"])
    except (TypeError, ValueError, KeyError) as exc:
        raise BadgeError("Разметка бейджа: нужны числа.") from exc
    if not (20 <= w <= 300 and 20 <= h <= 300 and 72 <= dpi <= 600):
        raise BadgeError("Размер карточки 20–300 мм, разрешение 72–600 DPI.")
    if pw <= 0 or ph <= 0 or px < 0 or py < 0 or px + pw > w or py + ph > h:
        raise BadgeError("Окно фото должно помещаться в карточку.")
    if not (0 <= x0 < x1 <= 1 and 0 <= y < 1 and 0 < lh < 1):
        raise BadgeError("Окно ФИО задаётся долями карточки от 0 до 1.")
    if not (1 <= min_pt <= max_pt <= 72):
        raise BadgeError("Кегль ФИО: минимальный не больше максимального, 1–72 пт.")
    return full


def _mm(value, dpi):
    return int(round(float(value) / 25.4 * dpi))


def card_size(layout):
    b = layout["badge"]
    return _mm(b["width_mm"], b["dpi"]), _mm(b["height_mm"], b["dpi"])


_font_path_cache = None


def font_path():
    """Первый доступный TTF с казахскими буквами; None — шрифта нет."""
    global _font_path_cache
    if _font_path_cache is not None:
        return _font_path_cache or None
    candidates = [settings.BADGE_FONT_PATH] if getattr(settings, "BADGE_FONT_PATH", "") else []
    candidates += FONT_CANDIDATES
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                font = ImageFont.truetype(path, 20)
                if all(font.getmask(ch).getbbox() for ch in KAZAKH_PROBE):
                    _font_path_cache = path
                    return path
            except OSError:
                continue
    logger.error("badge font with Kazakh letters not found")
    _font_path_cache = ""
    return None


def _font(size_px):
    path = font_path()
    if path:
        return ImageFont.truetype(path, size_px)
    return ImageFont.load_default(size_px)


def default_background(layout):
    """Стандартный фон: тёмная шапка «АККРЕДИТАЦИЯ» и светлое поле."""
    w, h = card_size(layout)
    img = Image.new("RGB", (w, h), "#f8fafc")
    draw = ImageDraw.Draw(img)
    head = int(h * 0.2)
    draw.rectangle([0, 0, w, head], fill="#1e3a8a")
    font = _font(int(head * 0.5))
    text = "АККРЕДИТАЦИЯ"
    tw = draw.textlength(text, font=font)
    draw.text(((w - tw) / 2, head * 0.22), text, font=font, fill="white")
    draw.rectangle([0, h - int(h * 0.05), w, h], fill="#1e3a8a")
    return img


def load_background(template, layout):
    """Фон шаблона, приведённый к размеру карточки, либо стандартный."""
    if template is not None and template.background:
        try:
            with template.background.open("rb") as fh:
                img = Image.open(fh)
                img.load()
            return ImageOps.fit(img.convert("RGB"), card_size(layout), Image.LANCZOS)
        except Exception:
            logger.error("badge background unreadable")
    return default_background(layout)


def _photo(attendee, size):
    """Фото участника, обрезанное по центру под окно; None — фото нет или не читается."""
    if not attendee.photo:
        return None
    try:
        with attendee.photo.open("rb") as fh:
            img = Image.open(fh)
            img.load()
        img = ImageOps.exif_transpose(img).convert("RGB")
        return ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.4))
    except Exception:
        return None


def badge_name(attendee, name_source):
    if name_source == "latin" and attendee.transcription:
        return attendee.transcription.strip()
    return " ".join(p for p in (attendee.surname, attendee.firstname) if p).strip()


def _wrap_two_lines(draw, text, font, max_width):
    """Уложить текст в одну или две строки шириной max_width; None — не помещается."""
    if draw.textlength(text, font=font) <= max_width:
        return [text]
    words = text.split()
    for cut in range(len(words) - 1, 0, -1):
        first, second = " ".join(words[:cut]), " ".join(words[cut:])
        if draw.textlength(first, font=font) <= max_width and draw.textlength(second, font=font) <= max_width:
            return [first, second]
    return None


def _draw_name(img, text, layout):
    n = layout["name"]
    w, h = img.size
    dpi = layout["badge"]["dpi"]
    draw = ImageDraw.Draw(img)
    x0, x1 = float(n["x0"]) * w, float(n["x1"]) * w
    max_width = x1 - x0
    line_h = float(n["line_height"]) * h
    pt = float(n["max_pt"])
    lines, font = None, None
    # Сначала перенос на вторую строку, и только потом уменьшение кегля.
    while pt >= float(n["min_pt"]):
        font = _font(max(1, int(round(pt / 72 * dpi))))
        lines = _wrap_two_lines(draw, text, font, max_width)
        if lines:
            break
        pt -= 0.5
    if not lines:
        lines = [text]
    y = float(n["y"]) * h
    for line in lines:
        draw.text((x0, y), line, font=font, fill=n.get("color") or "#111827")
        y += line_h


def render_card(attendee, background, layout, name_source):
    """Одна карточка (RGB) и признак «нет фото»."""
    img = background.copy()
    p = layout["photo"]
    dpi = layout["badge"]["dpi"]
    box = (_mm(p["x_mm"], dpi), _mm(p["y_mm"], dpi))
    size = (_mm(p["width_mm"], dpi), _mm(p["height_mm"], dpi))
    photo = _photo(attendee, size)
    missing = photo is None
    if missing:
        photo = Image.new("RGB", size, "#cbd5e1")
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=_mm(p["radius_mm"], dpi), fill=255)
    img.paste(photo, box, mask)
    _draw_name(img, badge_name(attendee, name_source), layout)
    return img, missing


def build_pdf(attendees, template, out, progress=None):
    """Собрать PDF (по странице на участника) в файловый объект `out`.

    Возвращает список предупреждений (участники без фото).
    """
    layout = validate_layout(template.layout if template else None)
    name_source = template.name_source if template else "ru"
    background = load_background(template, layout)
    dpi = layout["badge"]["dpi"]
    pages, warnings = [], []
    for i, attendee in enumerate(attendees, 1):
        card, missing = render_card(attendee, background, layout, name_source)
        if missing:
            warnings.append({"id": attendee.pk, "name": badge_name(attendee, "ru"), "problem": "no_photo"})
        pages.append(card)
        if progress and i % 25 == 0:
            progress(i)
    if not pages:
        raise BadgeError("Нет участников для печати.")
    if font_path() is None:
        warnings.append({"id": None, "name": "", "problem": "no_font"})
    pages[0].save(out, "PDF", resolution=dpi, save_all=True, append_images=pages[1:], quality=85)
    return warnings


def preview_png(attendee, template, layout=None):
    """PNG одной карточки для предпросмотра разметки (без записи о печати)."""
    full = validate_layout(layout if layout is not None else (template.layout if template else None))
    name_source = template.name_source if template else "ru"
    card, _ = render_card(attendee, load_background(template, full), full, name_source)
    buf = io.BytesIO()
    card.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def private_path(*parts):
    root = Path(settings.PRIVATE_FILES_ROOT)
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
