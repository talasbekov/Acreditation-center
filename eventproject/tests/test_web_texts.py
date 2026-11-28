"""Тексты Next.js (`web/lib/generated/`) не должны расходиться с источниками в Django."""

from django.test import SimpleTestCase

from eventproject.management.commands.export_web_texts import OUTPUT_DIR, build_files


class WebTextsUpToDateTests(SimpleTestCase):
    def test_generated_files_match_sources(self):
        for name, text in build_files().items():
            committed = (OUTPUT_DIR / name).read_text(encoding="utf-8").replace("\r\n", "\n")
            self.assertEqual(
                committed, text, f"web/lib/generated/{name} устарел: запустите manage.py export_web_texts"
            )
