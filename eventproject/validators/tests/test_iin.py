"""Story 3.1 — тесты ИИН-валидатора (≥20 кейсов, AC-6)."""

from datetime import date, datetime

from django.test import SimpleTestCase

from eventproject.validators.iin import ValidationResult, validate_iin

_W1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
_W2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]


def build_iin(yymmdd, century_gender, serial):
    """Собирает ИИН с корректной контрольной цифрой.

    yymmdd: 6 цифр, century_gender: 1 цифра, serial: 4 цифры.
    Контрольная цифра вычисляется тем же алгоритмом — тесты не зависят
    от «магических» чисел.
    """
    base = f"{yymmdd}{century_gender}{serial}"
    assert len(base) == 11, base
    d = [int(c) for c in base]
    control = sum(d[i] * _W1[i] for i in range(11)) % 11
    if control == 10:
        control = sum(d[i] * _W2[i] for i in range(11)) % 11
    assert control != 10, "serial без валидной контрольной цифры — выбери другой"
    return base + str(control)


class BuildHelperSanityTests(SimpleTestCase):
    def test_reference_male_xx(self):
        self.assertEqual(build_iin("851205", "3", "0123"), "851205301234")

    def test_reference_female_xxi(self):
        self.assertEqual(build_iin("010314", "6", "0007"), "010314600078")


class ValidIINTests(SimpleTestCase):
    def test_valid_male_xx_century(self):
        r = validate_iin("851205301234", date(1985, 12, 5))
        self.assertTrue(r.valid)
        self.assertEqual(r.error, "")

    def test_valid_female_xxi_century(self):
        self.assertTrue(validate_iin("010314600078", date(2001, 3, 14)).valid)

    def test_valid_male_xxi_century(self):
        iin = build_iin("050620", "5", "0042")  # 2005-06-20, муж
        self.assertTrue(validate_iin(iin, date(2005, 6, 20)).valid)

    def test_valid_female_xx_century(self):
        iin = build_iin("700101", "4", "0050")  # 1970-01-01, жен
        self.assertTrue(validate_iin(iin, date(1970, 1, 1)).valid)

    def test_valid_leap_day_2000(self):
        iin = build_iin("000229", "5", "0001")  # 2000-02-29 (високосный)
        self.assertTrue(validate_iin(iin, date(2000, 2, 29)).valid)

    def test_valid_birth_date_none_skips_compare(self):
        self.assertTrue(validate_iin("851205301234", None).valid)

    def test_datetime_birth_date_matches(self):
        # datetime (а не date) с тем же календарным днём должен считаться совпадением.
        r = validate_iin("851205301234", datetime(1985, 12, 5, 10, 30))
        self.assertTrue(r.valid)

    def test_control_digit_fallback_weights(self):
        # 851205301234 задействует fallback-веса (первый проход даёт остаток 10)
        self.assertTrue(validate_iin("851205301234", date(1985, 12, 5)).valid)


class NonResidentTests(SimpleTestCase):
    def test_none_is_valid(self):
        self.assertEqual(
            validate_iin(None, date(1990, 1, 1)), ValidationResult(True, "")
        )

    def test_empty_string_is_valid(self):
        self.assertTrue(validate_iin("", date(1990, 1, 1)).valid)

    def test_whitespace_is_valid(self):
        self.assertTrue(validate_iin("   ", date(1990, 1, 1)).valid)


class FormatErrorTests(SimpleTestCase):
    EXPECTED = "ИИН должен содержать ровно 12 цифр."

    def test_too_short(self):
        r = validate_iin("85120530123", date(1985, 12, 5))  # 11 цифр
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_too_long(self):
        r = validate_iin("8512053012345", date(1985, 12, 5))  # 13 цифр
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_non_digit_char(self):
        r = validate_iin("85120530123X", date(1985, 12, 5))
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_all_letters(self):
        r = validate_iin("abcdefghijkl", date(1985, 12, 5))
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_internal_space_len12(self):
        r = validate_iin("85120 301234", date(1985, 12, 5))  # 12 симв., но пробел
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)


class ControlDigitErrorTests(SimpleTestCase):
    EXPECTED = "ИИН некорректен: неверная контрольная цифра."

    def test_wrong_control_digit_male(self):
        r = validate_iin("851205301235", date(1985, 12, 5))  # должно быть ...4
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_wrong_control_digit_female(self):
        r = validate_iin("010314600070", date(2001, 3, 14))  # должно быть ...8
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_no_valid_control_digit_exists(self):
        # Префикс, где оба прохода весов дают остаток 10 → валидной контрольной
        # цифры не существует → ИИН отклоняется при любой последней цифре.
        for last in "0123456789":
            r = validate_iin("09409555729" + last, date(1994, 9, 4))
            self.assertFalse(r.valid)
            self.assertEqual(r.error, self.EXPECTED)

    def test_fallback_iin_wrong_check_digit(self):
        # 851205301234 — корректная контрольная (4) получена через fallback-веса.
        # Та же база с неверной цифрой должна отклоняться.
        r = validate_iin("851205301230", date(1985, 12, 5))
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)


class BirthDateMismatchTests(SimpleTestCase):
    def test_dob_mismatch_exact_message(self):
        r = validate_iin("851205301234", date(1985, 5, 12))
        self.assertFalse(r.valid)
        self.assertEqual(
            r.error,
            "Дата рождения в ИИН (05.12.1985) не совпадает "
            "с введённой (12.05.1985). Проверьте дату.",
        )

    def test_dob_mismatch_day(self):
        r = validate_iin("851205301234", date(1985, 12, 6))
        self.assertFalse(r.valid)
        self.assertIn("не совпадает", r.error)


class InvalidEncodedDateTests(SimpleTestCase):
    EXPECTED = "ИИН некорректен: недопустимая дата рождения."

    def test_invalid_month_13(self):
        iin = build_iin("851305", "3", "0123")  # месяц 13
        r = validate_iin(iin, date(1985, 12, 5))
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_feb_30(self):
        iin = build_iin("850230", "3", "0123")
        r = validate_iin(iin, date(1985, 2, 28))
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_feb_29_non_leap(self):
        iin = build_iin("850229", "3", "0123")  # 1985 не високосный
        r = validate_iin(iin, date(1985, 2, 28))
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_century_digit_zero(self):
        iin = build_iin("850101", "0", "0123")  # позиция 7 вне 1–6
        r = validate_iin(iin, date(1985, 1, 1))
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)

    def test_century_digit_nine(self):
        iin = build_iin("850101", "9", "0123")
        r = validate_iin(iin, date(1985, 1, 1))
        self.assertFalse(r.valid)
        self.assertEqual(r.error, self.EXPECTED)
