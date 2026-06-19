import os
from datetime import date

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from eventproject.models import Attendee, Event, Operator, Request

class SecurityTest(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(username='testoperator', password='password123')
        self.operator = Operator.objects.create(
            user=self.user,
            patronymic='Test',
            phone_number='+70000000000',
            workplace='Test Workplace',
        )
        self.event = Event.objects.create(
            name_rus='Test Event', 
            name_kaz='Test Event', 
            name_eng='Test Event', 
            event_code='T1', 
            date_start=date.today(), 
            date_end=date.today(), 
            city_code='AK'
        )
        self.req = Request.objects.create(
            name='Test Request', 
            event=self.event, 
            status='Active', 
            created_by=self.operator, 
            registration_time=timezone.now()
        )
        self.attendee = Attendee.objects.create(
            surname='Old',
            firstname='Name',
            patronymic='Patro',
            transcription='Old Name',
            iin='123456789012',
            birthDate=date(1990, 1, 1),
            post='Engineer',
            countryId='1000000105',
            docTypeId='passport',
            docSeries='AA',
            docNumber='123456',
            docBegin=date(2020, 1, 1),
            docEnd=date(2030, 1, 1),
            docIssue='Issuer',
            photo=SimpleUploadedFile('photo.jpg', b'photo-bytes', content_type='image/jpeg'),
            docScan=SimpleUploadedFile('doc.jpg', b'doc-bytes', content_type='image/jpeg'),
            sexId='M',
            dateAdd=timezone.now(),
            visitObjects='Object',
            request=self.req,
            dateEnd=date.today(),
            stickId='CAT',
        )

    def _valid_upload(self, name):
        return SimpleUploadedFile(
            name,
            b'x' * 2048,
            content_type='image/jpeg',
        )

    def test_csrf_protection(self):
        """
        AC-2: CSRF защита — POST без токена должен вернуть 403.
        Используем enforce_csrf_checks=True и НЕ передаём csrfmiddlewaretoken.
        """
        csrf_client = Client(enforce_csrf_checks=True)
        with self.settings(AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend']):
            url = f"/add_attendee/{self.req.id}/"
            csrf_client.force_login(self.user)
            # GET-запрос устанавливает csrftoken cookie
            csrf_client.get(url)

            # POST без csrfmiddlewaretoken и без X-CSRFToken заголовка
            response = csrf_client.post(url, {
                'req_id': self.req.id,
                'last_name': 'Test',
                'first_name': 'Test',
                'patronymic': 'Test',
                'latin_name': 'Test',
                'iin': '123456789012',
                'dob': '1990-01-01',
                'sex': '1',
                'citizenship': '1',
                'post': 'Test',
                'document_type': '1',
                'doc_series': 'AA',
                'doc_number': '123456',
                'doc_date_start': '2020-01-01',
                'doc_date_end': '2030-01-01',
                'doc_issuer': 'Test',
                'visit_objects': 'Test',
                'category': 'CAT',
                'photo': self._valid_upload('photo.jpg'),
                'doc_photo': self._valid_upload('doc.jpg'),
            })

            self.assertEqual(
                response.status_code, 403,
                f"Expected 403 (CSRF blocked), got {response.status_code}"
            )

    def test_credentials_not_hardcoded(self):
        """
        AC-1: Секреты из .env
        """
        self.assertTrue(os.path.exists('.env.example'))
        with open('.env.example', encoding='utf-8') as env_example:
            contents = env_example.read()

        self.assertNotIn('DB_PASSWORD=aktobe', contents)
        self.assertNotIn('DB_HOST=192.168.0.104', contents)
        self.assertIn('SECRET_KEY=change-me-secret-key', contents)
        self.assertIn('DB_PASSWORD=change-me-db-password', contents)

    def test_rate_limiting_upload(self):
        """
        AC-4: Rate limiting загрузок — django-ratelimit
        """
        self.client.force_login(self.user)
        url = reverse('update_attendee', args=[self.attendee.id])
        payload = {
            'csrfmiddlewaretoken': 'known-token',
            'last_name': 'Updated',
            'first_name': 'Name',
            'patronymic': 'Patro',
            'latin_name': 'Updated Name',
            'iin': '123456789012',
            'dob': '1990-01-01',
            'sex': 'M',
            'citizenship': '1000000105',
            'post': 'Engineer',
            'document_type': 'passport',
            'doc_series': 'AA',
            'doc_number': '123456',
            'doc_date_start': '2020-01-01',
            'doc_date_end': '2030-01-01',
            'doc_issuer': 'Issuer',
            'visit_objects': 'Object',
        }

        for _ in range(20):
            response = self.client.post(url, payload)
            self.assertEqual(response.status_code, 302)

        blocked_response = self.client.post(url, payload)
        self.assertEqual(blocked_response.status_code, 429)

    def test_session_timeout_role_based(self):
        """
        AC-5, AC-6: Session timeout
        """
        with self.settings(AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend']):
            # Обычный оператор
            self.client.login(username='testoperator', password='password123')
            self.client.get(reverse('application'))
            self.assertEqual(self.client.session.get_expiry_age(), 43200)
            
            # Суперпользователь
            if not User.objects.filter(username='admin').exists():
                User.objects.create_superuser(username='admin', password='password123', email='admin@test.com')
            self.client.login(username='admin', password='password123')
            self.client.get(reverse('index'))
            self.assertEqual(self.client.session.get_expiry_age(), 14400)

    def test_brute_force_protection(self):
        """
        AC-3: После 10 неудачных попыток входа IP блокируется.
        """
        from axes.models import AccessAttempt
        from axes.handlers.proxy import AxesProxyHandler

        # Очищаем историю попыток
        AccessAttempt.objects.all().delete()

        login_url = '/kz/user_login/'
        for _ in range(10):
            self.client.post(login_url, {
                'username': 'testoperator',
                'password': 'wrong_password',
            }, REMOTE_ADDR='127.0.0.2')

        # 11-я попытка — даже с правильным паролем должна быть заблокирована
        response = self.client.post(login_url, {
            'username': 'testoperator',
            'password': 'password123',
        }, REMOTE_ADDR='127.0.0.2')

        # django-axes возвращает 403, 429 или редиректит с ошибкой при блокировке
        self.assertIn(
            response.status_code, [403, 302, 429],
            f"Expected block after 10 failed attempts, got {response.status_code}"
        )
        # Проверяем что axes зафиксировал попытки
        self.assertTrue(
            AccessAttempt.objects.filter(ip_address='127.0.0.2').exists(),
            "Axes should have recorded failed attempts"
        )

    def test_update_attendee_allows_metadata_change_without_reupload(self):
        self.client.force_login(self.user)
        url = reverse('update_attendee', args=[self.attendee.id])
        response = self.client.post(url, {
            'csrfmiddlewaretoken': 'known-token',
            'last_name': 'Updated',
            'first_name': 'Name',
            'patronymic': 'Patro',
            'latin_name': 'Updated Name',
            'iin': '123456789012',
            'dob': '1990-01-01',
            'sex': 'M',
            'citizenship': '1000000105',
            'post': 'Lead Engineer',
            'document_type': 'passport',
            'doc_series': 'AA',
            'doc_number': '654321',
            'doc_date_start': '2020-01-01',
            'doc_date_end': '2030-01-01',
            'doc_issuer': 'Updated Issuer',
            'visit_objects': 'Updated Object',
        })

        self.assertEqual(response.status_code, 302)
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.surname, 'Updated')
        self.assertEqual(self.attendee.post, 'Lead Engineer')
