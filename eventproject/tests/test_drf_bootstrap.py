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
    def test_validation_error_is_rendered_in_rfc7807_format(self):
        from rest_framework.exceptions import ValidationError

        from eventproject.api.exceptions import rfc7807_exception_handler

        response = rfc7807_exception_handler(
            ValidationError({"name": ["This field is required."]}),
            {"view": None, "args": (), "kwargs": {}, "request": None},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                "type": "https://httpstatuses.com/400",
                "title": "Bad Request",
                "detail": "name: This field is required.",
                "field": "name",
            },
        )


class CacheRoundTripTests(TestCase):
    def test_cache_round_trip(self):
        cache.set("test_key", "test_value", 60)

        self.assertEqual(cache.get("test_key"), "test_value")
