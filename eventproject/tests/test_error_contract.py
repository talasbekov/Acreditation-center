"""Story fe-1.1 (AC-2/AC-3) — backend-сторона контракта ошибок.

Гарантии:
  • анти-дрейф: вывод `export_error_codes` == закоммиченный `errors.codes.json`;
  • зеркало: множество кодов реестра == ключи `errors.json` (та же проверка, что в
    vitest-тесте, но со стороны Python — ловит рассинхрон без запуска фронта);
  • сэмплы round-trip фикстуры — реальной формы (type из реестра, params dict, field).
Дополняет vitest `errorContract.test.ts` (zod-сторона).
"""

import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from eventproject.errors.registry import ERROR_CODES
from eventproject.errors.samples import build_samples
from eventproject.management.commands.export_error_codes import build_payload, serialize

_ERRORS_DIR = Path(settings.BASE_DIR) / "frontend" / "src" / "errors"
_CODES_FILE = _ERRORS_DIR / "errors.codes.json"
_DICT_FILE = _ERRORS_DIR / "errors.json"
_SAMPLES_FILE = _ERRORS_DIR / "__fixtures__" / "drf-error-samples.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ErrorCodesExportDriftTests(SimpleTestCase):
    def test_committed_codes_json_matches_registry_export(self):
        # Анти-дрейф: errors.codes.json пересобирается командой 1:1 из реестра.
        self.assertTrue(
            _CODES_FILE.exists(),
            "errors.codes.json отсутствует — запусти `manage.py export_error_codes`",
        )
        self.assertEqual(
            _CODES_FILE.read_text(encoding="utf-8"),
            serialize(build_payload()),
            "errors.codes.json расходится с реестром — пере-экспортируй командой",
        )


class ErrorContractMirrorTests(SimpleTestCase):
    def test_registry_codes_equal_errors_json_keys(self):
        # Равенство множеств в обе стороны (та же инвариантность, что в vitest).
        registry = set(ERROR_CODES)
        dict_keys = set(_load(_DICT_FILE))
        self.assertEqual(registry - dict_keys, set(), "коды реестра без ключа в errors.json")
        self.assertEqual(dict_keys - registry, set(), "ключи errors.json без кода в реестре")

    def test_errors_json_has_three_locales(self):
        # ru — источник; kz/en — стаб (юридически значимые ждут носителя).
        data = _load(_DICT_FILE)
        for code, value in data.items():
            self.assertEqual(set(value), {"ru", "kz", "en"}, code)


class ErrorSamplesFixtureTests(SimpleTestCase):
    def test_samples_are_real_shape_with_known_types(self):
        samples = _load(_SAMPLES_FILE)
        self.assertGreater(len(samples), 0)
        for s in samples:
            self.assertEqual(set(s) >= {"type", "field", "params"}, True, s)
            self.assertIn(s["type"], ERROR_CODES, f"type {s['type']} вне реестра")
            self.assertIsInstance(s["params"], dict)

    def test_samples_match_live_handler_output(self):
        # Анти-дрейф round-trip: фикстура == свежий вывод live handler (build_samples).
        # Если handler-shape изменится — фикстура краснеет, а не молча устаревает.
        committed = _load(_SAMPLES_FILE)
        fresh = json.loads(json.dumps(build_samples(), ensure_ascii=False))
        self.assertEqual(
            committed, fresh,
            "drf-error-samples.json расходится с live handler — регенерируй из build_samples()",
        )
