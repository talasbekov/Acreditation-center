from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from qr_event.models import QrIin

# Валидный ИИН: 18.01.1995, код века 3, контрольная цифра 7
VALID_IIN = "950118301007"


class QrEventSecurityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="op1", password="pass12345")
        self.other = User.objects.create_user(username="op2", password="pass12345")

    def test_anonymous_cannot_access_iin_form(self):
        response = self.client.get(reverse("iin_form"), secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/user_login/", response.url)

    def test_anonymous_cannot_access_success_page(self):
        response = self.client.get(reverse("qr_success", kwargs={"pk": 1}), secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/user_login/", response.url)

    def test_qr_filename_does_not_contain_iin(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("iin_form"), {"iin": VALID_IIN}, secure=True)
        self.assertEqual(response.status_code, 302)
        obj = QrIin.objects.get()
        self.assertNotIn(VALID_IIN, obj.qr_code.name)

    def test_iin_stored_encrypted_at_rest(self):
        self.client.force_login(self.user)
        self.client.post(reverse("iin_form"), {"iin": VALID_IIN}, secure=True)
        obj = QrIin.objects.get()
        self.assertEqual(obj.iin, VALID_IIN)  # прозрачная расшифровка через ORM
        with connection.cursor() as cursor:
            cursor.execute("SELECT iin FROM qr_event_qriin WHERE id = %s", [obj.pk])
            raw = cursor.fetchone()[0]
        self.assertNotIn(VALID_IIN, str(raw))

    def test_success_page_not_enumerable_by_other_user(self):
        self.client.force_login(self.user)
        self.client.post(reverse("iin_form"), {"iin": VALID_IIN}, secure=True)
        obj = QrIin.objects.get()

        # Создатель видит свою запись
        response = self.client.get(reverse("qr_success", kwargs={"pk": obj.pk}), secure=True)
        self.assertEqual(response.status_code, 200)

        # Другой аутентифицированный пользователь — нет (анти-IDOR)
        self.client.logout()
        self.client.force_login(self.other)
        response = self.client.get(reverse("qr_success", kwargs={"pk": obj.pk}), secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("iin_form"))

    def test_invalid_iin_rejected(self):
        self.client.force_login(self.user)
        # неверная контрольная цифра
        response = self.client.post(reverse("iin_form"), {"iin": "950118301008"}, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QrIin.objects.count(), 0)
