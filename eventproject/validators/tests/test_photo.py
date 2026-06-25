"""Story 5.3 — тесты валидатора фото/документа (validators/photo.py).

Единый валидатор переиспользуется для photo и docScan (последний — после PDF→JPEG).
Покрываем границы: ratio (вертикальность), разрешение, размер, не-изображение,
а также PDF-детект и конвертацию первой страницы в JPEG.
"""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import serializers

from eventproject.validators.photo import (
    ERR_LOW_RES,
    ERR_NOT_IMAGE,
    ERR_NOT_VERTICAL,
    ERR_PDF_FAILED,
    ERR_TOO_BIG,
    ERR_TOO_MANY_PIXELS,
    convert_pdf_to_jpeg,
    is_pdf,
    validate_image_file,
)


def _img_bytes(width, height, fmt="JPEG"):
    buf = BytesIO()
    Image.new("RGB", (width, height), (120, 120, 120)).save(buf, format=fmt)
    return buf.getvalue()


def _upload(width, height, name="p.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, _img_bytes(width, height), content_type=content_type)


class ValidateImageFileTests(TestCase):
    def _assert_rejects(self, upload, expected_msg):
        with self.assertRaises(serializers.ValidationError) as cm:
            validate_image_file(upload)
        self.assertIn(expected_msg, str(cm.exception.detail))

    def test_valid_vertical_passes(self):
        validate_image_file(_upload(600, 800))  # 3×4, ровно минимум — без ошибки

    def test_ratio_boundary_085_passes(self):
        # 680/800 = 0.85 ровно — граница включительно проходит.
        validate_image_file(_upload(680, 800))

    def test_horizontal_rejected(self):
        self._assert_rejects(_upload(800, 600), ERR_NOT_VERTICAL)

    def test_square_rejected(self):
        self._assert_rejects(_upload(800, 800), ERR_NOT_VERTICAL)

    def test_low_width_rejected(self):
        self._assert_rejects(_upload(599, 800), ERR_LOW_RES)

    def test_low_height_rejected(self):
        self._assert_rejects(_upload(600, 799), ERR_LOW_RES)

    def test_oversize_rejected(self):
        # Размер проверяется ПЕРВЫМ (до открытия Pillow) — байты могут быть любыми.
        big = SimpleUploadedFile(
            "big.jpg", b"\x00" * (5 * 1024 * 1024 + 1), content_type="image/jpeg"
        )
        self._assert_rejects(big, ERR_TOO_BIG)

    def test_not_image_rejected(self):
        bad = SimpleUploadedFile("x.jpg", b"this is not an image", content_type="image/jpeg")
        self._assert_rejects(bad, ERR_NOT_IMAGE)

    # ── code-review patch: анти-decompression-bomb (лимит пикселей) ──────
    @override_settings(PHOTO_MAX_PIXELS=1000)
    def test_too_many_pixels_rejected(self):
        # 600×800 = 480000 px > лимит 1000 → отклонено ДО декодирования.
        self._assert_rejects(_upload(600, 800), ERR_TOO_MANY_PIXELS)

    # ── code-review patch: усечённый/битый файл ловится (img.load) ───────
    def test_truncated_image_rejected(self):
        data = _img_bytes(600, 800)
        truncated = data[: len(data) // 2]  # валидный заголовок, обрезанные пиксели
        bad = SimpleUploadedFile("t.jpg", truncated, content_type="image/jpeg")
        self._assert_rejects(bad, ERR_NOT_IMAGE)


class PdfHelpersTests(TestCase):
    def _pdf_bytes(self, width=600, height=800):
        buf = BytesIO()
        Image.new("RGB", (width, height), (200, 200, 200)).save(buf, format="PDF")
        return buf.getvalue()

    def test_is_pdf_true_by_signature(self):
        up = SimpleUploadedFile("d.pdf", self._pdf_bytes(), content_type="application/pdf")
        self.assertTrue(is_pdf(up))

    def test_is_pdf_false_for_jpeg(self):
        self.assertFalse(is_pdf(_upload(600, 800)))

    def test_convert_pdf_to_jpeg_returns_vertical_jpeg(self):
        up = SimpleUploadedFile("d.pdf", self._pdf_bytes(600, 800), content_type="application/pdf")
        out = convert_pdf_to_jpeg(up)
        self.assertTrue(out.name.endswith(".jpg"))
        img = Image.open(out)
        self.assertEqual(img.format, "JPEG")
        w, h = img.size
        self.assertLess(w / h, 1.0)  # вертикальность сохранена

    def test_converted_pdf_passes_image_validation(self):
        # AC-4: PDF→JPEG, далее проходит ту же валидацию, что и фото.
        up = SimpleUploadedFile("d.pdf", self._pdf_bytes(600, 800), content_type="application/pdf")
        out = convert_pdf_to_jpeg(up)
        validate_image_file(out)  # без ошибки

    # ── code-review patch: битый PDF → понятное 400, не 500 ──────────────
    def test_convert_garbage_pdf_returns_pdf_failed(self):
        bad = SimpleUploadedFile(
            "x.pdf", b"%PDF-1.4\nnot a real pdf", content_type="application/pdf"
        )
        with self.assertRaises(serializers.ValidationError) as cm:
            convert_pdf_to_jpeg(bad)
        self.assertIn(ERR_PDF_FAILED, str(cm.exception.detail))

    # ── P1-7: сконвертированный из PDF растр капается по мегапикселям ─────
    @override_settings(PHOTO_MAX_PIXELS=1000)
    def test_pdf_render_exceeding_pixel_cap_rejected(self):
        # Рендер PDF (>1000 px при dpi=150) отклоняется ДО декода в RGB → не 500,
        # не decompression-bomb. Капы: convert_pdf_to_jpeg (до RGB) + validate_image_file.
        up = SimpleUploadedFile(
            "big.pdf", self._pdf_bytes(600, 800), content_type="application/pdf"
        )
        with self.assertRaises(serializers.ValidationError) as cm:
            convert_pdf_to_jpeg(up)
        self.assertIn(ERR_PDF_FAILED, str(cm.exception.detail))
