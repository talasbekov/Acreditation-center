"""Story 3.2 — тесты residency-логики (AC-6)."""

from datetime import date

from django.test import SimpleTestCase, override_settings

from eventproject.validators.residency import (
    is_resident_country,
    resolve_residency,
)

KZ = "1000000105"
OTHER = "2000000200"
VALID_IIN = "851205301234"  # 1985-12-05, муж (Story 3.1)
BDATE = date(1985, 12, 5)


@override_settings(KZ_COUNTRY_ID=KZ)
class IsResidentCountryTests(SimpleTestCase):
    def test_kz_is_resident(self):
        self.assertTrue(is_resident_country(KZ))

    def test_kz_with_whitespace(self):
        self.assertTrue(is_resident_country("  1000000105  "))

    def test_other_country_not_resident(self):
        self.assertFalse(is_resident_country(OTHER))

    def test_none_not_resident(self):
        self.assertFalse(is_resident_country(None))


@override_settings(KZ_COUNTRY_ID=KZ)
class ResidentRulesTests(SimpleTestCase):
    def test_resident_valid_iin(self):
        r = resolve_residency(KZ, VALID_IIN, BDATE)
        self.assertTrue(r.is_resident)
        self.assertEqual(r.iin, VALID_IIN)
        self.assertEqual(r.error, "")

    def test_resident_iin_normalized(self):
        r = resolve_residency(KZ, f"  {VALID_IIN}  ", BDATE)
        self.assertTrue(r.is_resident)
        self.assertEqual(r.iin, VALID_IIN)
        self.assertEqual(r.error, "")

    def test_resident_missing_iin(self):
        r = resolve_residency(KZ, None, BDATE)
        self.assertTrue(r.is_resident)
        self.assertIsNone(r.iin)
        self.assertEqual(r.error, "ИИН обязателен для граждан Казахстана")

    def test_resident_empty_iin(self):
        r = resolve_residency(KZ, "", BDATE)
        self.assertTrue(r.is_resident)
        self.assertIsNone(r.iin)
        self.assertEqual(r.error, "ИИН обязателен для граждан Казахстана")

    def test_resident_invalid_iin_returns_validator_message(self):
        r = resolve_residency(KZ, "851205301235", BDATE)  # неверная контрольная
        self.assertTrue(r.is_resident)
        self.assertEqual(r.error, "ИИН некорректен: неверная контрольная цифра.")

    def test_resident_iin_dob_mismatch(self):
        r = resolve_residency(KZ, VALID_IIN, date(1985, 5, 12))
        self.assertTrue(r.is_resident)
        self.assertIn("не совпадает", r.error)

    def test_resident_invalid_iin_preserves_normalized_iin(self):
        # При невалидном ИИН резидента нормализованный ИИН сохраняется в результате.
        r = resolve_residency(KZ, f"  851205301235  ", BDATE)
        self.assertTrue(r.is_resident)
        self.assertEqual(r.iin, "851205301235")
        self.assertNotEqual(r.error, "")

    def test_resident_garbage_iin_routes_to_validator(self):
        # Непустой мусор уходит в validate_iin (формат), а не в ветку «обязателен».
        r = resolve_residency(KZ, "not-an-iin", BDATE)
        self.assertTrue(r.is_resident)
        self.assertEqual(r.error, "ИИН должен содержать ровно 12 цифр.")


class AmbientSettingTests(SimpleTestCase):
    def test_uses_configured_kz_country_id(self):
        # Без override_settings — полагается на settings.KZ_COUNTRY_ID (default "1000000105").
        self.assertTrue(is_resident_country("1000000105"))
        r = resolve_residency("1000000105", VALID_IIN, BDATE)
        self.assertTrue(r.is_resident)
        self.assertEqual(r.iin, VALID_IIN)


@override_settings(KZ_COUNTRY_ID="  1000000105  ")
class KzSettingWhitespaceTests(SimpleTestCase):
    def test_setting_whitespace_tolerated(self):
        # P1: значение setting стрипается → пробелы в env не ломают резидентство.
        self.assertTrue(is_resident_country("1000000105"))


@override_settings(KZ_COUNTRY_ID=KZ)
class NonResidentRulesTests(SimpleTestCase):
    def test_non_resident_no_iin(self):
        r = resolve_residency(OTHER, None, None)
        self.assertFalse(r.is_resident)
        self.assertIsNone(r.iin)
        self.assertEqual(r.error, "")

    def test_non_resident_iin_ignored(self):
        # Переключение РК→не-РК: переданный ИИН очищается, не сохраняется (AC-3).
        r = resolve_residency(OTHER, VALID_IIN, BDATE)
        self.assertFalse(r.is_resident)
        self.assertIsNone(r.iin)
        self.assertEqual(r.error, "")

    def test_non_resident_invalid_iin_still_ignored(self):
        r = resolve_residency(OTHER, "not-an-iin", None)
        self.assertFalse(r.is_resident)
        self.assertIsNone(r.iin)
        self.assertEqual(r.error, "")
