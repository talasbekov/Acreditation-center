"""The release image is built from an allowlist (.dockerignore).

A stylesheet or script that a template links but the allowlist omits is silently
missing from the image: the page loads unstyled and only the browser sees a 404.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE = Path(settings.BASE_DIR)
STATIC_TAG = re.compile(r"""\{%\s*static\s+['"]([^'"]+)['"]""")


def _allowlisted():
    lines = (BASE / ".dockerignore").read_text(encoding="utf-8").splitlines()
    return {line.strip()[1:] for line in lines if line.strip().startswith("!")}


def _template_static_refs():
    refs = {}
    for template in (BASE / "templates").rglob("*.html"):
        for name in STATIC_TAG.findall(template.read_text(encoding="utf-8")):
            refs.setdefault(name, template.name)
    return refs


class ReleaseStaticInputsTests(SimpleTestCase):
    def test_every_linked_static_file_reaches_the_image(self):
        allowed = _allowlisted()
        missing = sorted(
            f"static/{name} (из {template})"
            for name, template in _template_static_refs().items()
            if (BASE / "static" / name).is_file() and f"static/{name}" not in allowed
        )
        self.assertEqual(missing, [], "Добавьте в .dockerignore: " + ", ".join(missing))

    def test_every_linked_static_file_exists(self):
        absent = sorted(
            f"static/{name} (из {template})"
            for name, template in _template_static_refs().items()
            if not (BASE / "static" / name).is_file()
        )
        self.assertEqual(absent, [], "Шаблоны ссылаются на несуществующие файлы: " + ", ".join(absent))
