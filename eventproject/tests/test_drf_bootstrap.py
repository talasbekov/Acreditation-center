from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import resolve


class APIRouteTests(SimpleTestCase):
    def test_api_v1_prefix_is_registered(self):
        match = resolve("/api/v1/")

        self.assertEqual(match.route, "api/v1/")


class DRFSettingsTests(SimpleTestCase):
    def test_session_authentication_is_default(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"],
            ["rest_framework.authentication.SessionAuthentication"],
        )

    def test_rfc7807_handler_is_configured(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["EXCEPTION_HANDLER"],
            "eventproject.api.exceptions.rfc7807_exception_handler",
        )

    def test_cors_middleware_is_registered_before_common_middleware(self):
        middleware = list(settings.MIDDLEWARE)

        self.assertIn("corsheaders.middleware.CorsMiddleware", middleware)
        self.assertLess(
            middleware.index("corsheaders.middleware.CorsMiddleware"),
            middleware.index("django.middleware.common.CommonMiddleware"),
        )


class RFC7807HandlerTests(SimpleTestCase):
    """Story fe-1.1 — машинный `type` (код) + `params` + `field` вместо локализованной прозы."""

    _ctx = {"view": None, "args": (), "kwargs": {}, "request": None}

    def _handle(self, exc):
        from eventproject.api.exceptions import rfc7807_exception_handler

        return rfc7807_exception_handler(exc, self._ctx)

    def test_fallback_extracts_machine_code_from_errordetail(self):
        # Обычный DRF ValidationError → код из ErrorDetail.code (здесь дефолтный "invalid"),
        # field из ключа, params={}, detail сохранён (дефолтный язык, для логов/не-UI).
        from rest_framework.exceptions import ErrorDetail, ValidationError

        response = self._handle(
            ValidationError({"name": [ErrorDetail("This field is required.", code="required")]})
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                "type": "required",
                "field": "name",
                "params": {},
                "detail": "name: This field is required.",
            },
        )

    def test_coded_validation_error_carries_code_and_params(self):
        # CodedValidationError несёт динамические params (iin_dob_mismatch) нетронутыми.
        from eventproject.errors import coded_error

        response = self._handle(
            coded_error("iin_dob_mismatch", field="iin", iin_dob="05.12.1985", entered_dob="12.05.1985")
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["type"], "iin_dob_mismatch")
        self.assertEqual(response.data["field"], "iin")
        self.assertEqual(
            response.data["params"], {"iin_dob": "05.12.1985", "entered_dob": "12.05.1985"}
        )
        # detail — дефолтный язык, только логи/не-UI (НЕ источник UI-текста).
        self.assertIn("05.12.1985", response.data["detail"])

    def test_no_localized_title_or_prose_as_ui_source(self):
        # Контракт R1: нет человекочитаемого `title`; type — машинный, не status-URL.
        from eventproject.errors import coded_error

        data = self._handle(coded_error("iin_checksum", field="iin")).data
        self.assertNotIn("title", data)
        self.assertEqual(data["type"], "iin_checksum")
        self.assertEqual(data["params"], {})


class CacheRoundTripTests(TestCase):
    def test_cache_round_trip(self):
        cache.set("test_key", "test_value", 60)

        self.assertEqual(cache.get("test_key"), "test_value")
