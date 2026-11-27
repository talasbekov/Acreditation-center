from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from eventproject.models import Event, Operator, Request
from eventproject.views.integration import integrate, integrate_kazenergy


class DisabledPartnerTests(TestCase):
    def test_missing_credentials_create_no_import_request(self):
        user = get_user_model().objects.create(username="synthetic-admin", is_superuser=True)
        operator = Operator.objects.create(user=user)
        event = Event.objects.create(name_rus="Synthetic")
        factory = RequestFactory()
        request = factory.post("/")
        request.user = user
        with patch.object(integrate, "AVALON_API_KEY", ""):
            response = async_to_sync(integrate.kazexpo_receive)(request, event.pk)
            self.assertEqual(response.status_code, 503)
        with patch.object(integrate_kazenergy, "API_KEY", ""):
            response = async_to_sync(integrate_kazenergy.kazenergy_receive)(factory.get("/"), event.pk, operator.pk)
            self.assertEqual(response.status_code, 503)
        self.assertFalse(Request.objects.exists())
