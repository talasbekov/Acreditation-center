"""Синтетические вложения, проходящие правила фото и скана (≥ 600×800, 3×4)."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def jpeg_bytes(width=600, height=800, color=(120, 120, 120)):
    buffer = BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def valid_jpeg(name="photo.jpg", **kwargs):
    return SimpleUploadedFile(name, jpeg_bytes(**kwargs), content_type="image/jpeg")
