"""P0-1: URL pattern names must be unique so ``reverse()`` / ``{% url %}`` resolve
deterministically.

Before the fix, the RU/KZ/EN localized routes shared the same ``name=`` values, so
``reverse("user_login")`` returned the *last* matching pattern (the ``/en/`` route) and
default-locale (RU) callers were silently routed to the English handlers. These tests
pin every canonical name to its default (RU) route and give the localized routes their
own unique names.
"""
from django.test import SimpleTestCase
from django.urls import reverse


class CanonicalNameResolutionTests(SimpleTestCase):
    def test_user_login_resolves_to_default_route(self):
        self.assertEqual(reverse("user_login"), "/user_login/")

    def test_application_resolves_to_default_route(self):
        self.assertEqual(reverse("application"), "/application/")

    def test_logout_resolves_to_default_route(self):
        self.assertEqual(reverse("logout"), "/logout/")

    def test_change_password_resolves_to_default_route(self):
        self.assertEqual(reverse("change_password"), "/change_password/")

    def test_create_request_resolves_to_default_route(self):
        self.assertEqual(reverse("create_request", args=[1]), "/create/1/")

    def test_show_request_resolves_to_default_route(self):
        self.assertEqual(reverse("show_request", args=[1]), "/show/1/")

    def test_add_attendee_resolves_to_default_route(self):
        self.assertEqual(reverse("add_attendee", args=[1]), "/add_attendee/1/")

    def test_back_to_change_resolves_to_default_route(self):
        self.assertEqual(reverse("back_to_change", args=[1]), "/back_to_change/1/")

    def test_preview_resolves_to_default_route(self):
        self.assertEqual(reverse("preview", args=[1]), "/preview/1/")

    def test_send_resolves_to_default_route(self):
        self.assertEqual(reverse("send", args=[1]), "/send/1/")

    def test_delete_attendee_resolves_to_default_route(self):
        self.assertEqual(reverse("delete_attendee"), "/delete_attendee/")

    def test_delete_request_resolves_to_default_route(self):
        self.assertEqual(reverse("delete_request", args=[1]), "/delete_request/1/")


class LocalizedNameResolutionTests(SimpleTestCase):
    def test_kz_user_login_named(self):
        self.assertEqual(reverse("kz_user_login"), "/kz/user_login/")

    def test_en_user_login_named(self):
        self.assertEqual(reverse("en_user_login"), "/en/user_login/")

    def test_kz_application_named(self):
        self.assertEqual(reverse("kz_application"), "/kz/application/")

    def test_en_application_named(self):
        self.assertEqual(reverse("en_application"), "/en/application/")

    def test_kz_add_attendee_named(self):
        self.assertEqual(reverse("kz_add_attendee", args=[1]), "/kz/add_attendee/1/")

    def test_en_delete_request_named(self):
        self.assertEqual(reverse("en_delete_request", args=[1]), "/en/delete_request/1/")
