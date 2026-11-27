from datetime import date
import re
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings

from eventproject.models import Event, Operator


@override_settings(
    OPERATOR_PUBLIC_ORIGIN="https://operator.example.test",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class OperatorActivationHTMLTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin-test", "admin@example.test", "test-admin-password")
        self.client.force_login(self.admin, backend="django.contrib.auth.backends.ModelBackend")
        self.event = Event.objects.create(name_rus="Тест", date_start=date.today(), date_end=date.today())

    def create_from_form(self):
        return self.client.post("/add_operator/", {
            "login": "recipient", "email": "recipient@example.test",
            "first_name": "Test", "last_name": "Recipient", "patronymic": "",
            "workplace": "", "phone_number": "", "event_code": self.event.pk,
        })

    def test_create_and_activate_once(self):
        created = self.create_from_form()
        self.assertContains(created, "Ссылка для установки пароля")
        user = User.objects.get(username="recipient")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.operator.events.filter(pk=self.event.pk).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["recipient@example.test"])
        link = re.search(r"https://\S+", mail.outbox[0].body).group()
        self.assertNotIn(link, created.content.decode())
        self.assertEqual(urlsplit(link).netloc, "operator.example.test")
        owner = Client()
        form = owner.get(urlsplit(link).path)
        self.assertEqual(form.status_code, 302)
        self.assertIn("/set-password/", form.url)
        self.assertEqual(form.headers.get("Referrer-Policy"), "no-referrer")
        self.assertIn("no-store", form.headers["Cache-Control"])
        token = urlsplit(link).path.rstrip("/").rsplit("/", 1)[1]
        self.assertNotIn(token, form.url)
        page = owner.get(form.url)
        self.assertEqual(page.headers.get("Referrer-Policy"), "no-referrer")
        self.assertNotIn(token.encode(), page.content)
        self.assertContains(page, "new_password1")
        password = "test-receiver-fresh-passphrase!"
        saved = owner.post(form.url, {"new_password1": password, "new_password2": password})
        self.assertRedirects(saved, "/user_login/", fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.check_password(password))
        self.assertFalse(Client().get(urlsplit(link).path).context["validlink"])

    def test_admin_reset_requires_csrf_post_and_keeps_current_password(self):
        user = User.objects.create_user("existing", "existing@example.test", "old-test-password")
        Operator.objects.create(user=user)
        original_hash = user.password
        owner = Client()
        owner.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
        path = "/new_password/existing/"
        self.assertEqual(self.client.get(path).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(csrf.post(path).status_code, 403)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(self.client.post(path), "Ссылка для установки пароля отправлена")
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)
        self.assertEqual(len(mail.outbox), 1)
        with patch("eventproject.operator_activation.send_mail", side_effect=OSError):
            self.assertContains(self.client.post(path), "Письмо не отправлено")
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)
        self.assertEqual(owner.get("/user_login/").wsgi_request.user.pk, user.pk)

    def test_login_pages_load_draft_cleanup(self):
        client = Client()
        for path in ("/user_login/", "/kz/user_login/", "/en/user_login/"):
            with self.subTest(path=path):
                self.assertContains(client.get(path), "js/clear-attendee-draft.js")

    def test_console_file_and_invalid_origin_receive_no_message(self):
        user = User.objects.create_user("existing", "existing@example.test", "old-test-password")
        Operator.objects.create(user=user)
        with patch("eventproject.operator_activation.send_mail") as sender:
            for backend in ("console", "filebased", "dummy"):
                with self.subTest(backend=backend), self.settings(EMAIL_BACKEND=f"django.core.mail.backends.{backend}.EmailBackend"):
                    self.assertContains(self.client.post("/new_password/existing/"), "Письмо не отправлено")
            for origin in ("", "http://operator.example.test", "https://user@operator.example.test", "https://operator.example.test/path"):
                with self.subTest(origin=origin), self.settings(OPERATOR_PUBLIC_ORIGIN=origin):
                    self.assertContains(self.client.post("/new_password/existing/"), "Письмо не отправлено")
            sender.assert_not_called()

    def test_link_invalid_after_privilege_change_and_expiry(self):
        from datetime import datetime, timedelta

        user = User.objects.create_user("existing", "existing@example.test", "old-test-password")
        Operator.objects.create(user=user)
        issued = datetime(2026, 1, 1)
        with patch("eventproject.operator_activation.operator_tokens._now", return_value=issued):
            self.client.post("/new_password/existing/")
        path = urlsplit(re.search(r"https://\S+", mail.outbox[0].body).group()).path
        with patch("eventproject.operator_activation.operator_tokens._now", return_value=issued + timedelta(days=5)):
            self.assertFalse(Client().get(path).context["validlink"])
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        with patch("eventproject.operator_activation.operator_tokens._now", return_value=issued):
            self.assertFalse(Client().get(path).context["validlink"])
