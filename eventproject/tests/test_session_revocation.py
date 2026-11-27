from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from eventproject.models import Event, Operator, UserSessionGeneration
from eventproject.operator_activation import operator_tokens
from eventproject.services.session_revocation import SESSION_GENERATION_KEY



def _migrate_to_latest():
    """Restore the full schema for later tests, whatever the newest migration is."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())

class SessionRevocationTests(TestCase):
    def setUp(self):
        admin = User.objects.create_superuser("registry-admin", email="admin@example.invalid")
        self.client.force_login(admin, backend="django.contrib.auth.backends.ModelBackend")
        self.user = User.objects.create_user("recipient", password="fixture-login-passphrase")
        self.operator = Operator.objects.create(user=self.user)
        self.browser = Client()
        self.sign_in()

    def sign_in(self):
        self.assertEqual(self.browser.post("/user_login/", {
            "username": self.user.username, "password": "fixture-login-passphrase",
        }).status_code, 302)

    def signed_in(self):
        return self.browser.get("/user_login/").wsgi_request.user.is_authenticated

    def set_active(self, active):
        action = "reactivate" if active else "deactivate"
        response = self.client.post(reverse("operator-" + action, args=[self.operator.pk]))
        self.assertEqual(response.status_code, 200)

    def test_idle_session_requires_a_new_login_after_reactivation(self):
        self.set_active(False)
        self.set_active(True)
        self.assertFalse(self.signed_in())
        self.sign_in()
        self.assertTrue(self.signed_in())

    def test_access_while_inactive_does_not_revive_after_reactivation(self):
        self.set_active(False)
        self.assertFalse(self.signed_in())
        self.set_active(True)
        self.assertFalse(self.signed_in())

    def test_unaffected_predeployment_session_survives_but_known_revocation_requires_login(self):
        session = self.browser.session
        session.pop(SESSION_GENERATION_KEY)
        session.save()
        self.assertTrue(self.signed_in())
        self.set_active(False)
        self.set_active(True)
        self.assertFalse(self.signed_in())

    def test_failure_recording_deactivation_leaves_status_and_session_unchanged(self):
        with patch("eventproject.views.operator_api.record_access_event", side_effect=RuntimeError("fixture failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("operator-deactivate", args=[self.operator.pk]))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(UserSessionGeneration.objects.filter(user=self.user).exists())
        self.assertTrue(self.signed_in())

    def test_operator_invitation_is_not_reactivated_after_an_account_revocation(self):
        token = operator_tokens.make_token(self.user)
        self.assertTrue(operator_tokens.check_token(self.user, token))
        self.set_active(False)
        self.set_active(True)
        self.user.refresh_from_db()
        self.assertFalse(operator_tokens.check_token(self.user, token))
        self.assertTrue(operator_tokens.check_token(self.user, operator_tokens.make_token(self.user)))

    def test_admin_revokes_a_staff_account_without_an_operator_profile(self):
        self.operator.delete()
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        url = reverse("admin:auth_user_change", args=[self.user.pk])
        data = {
            "username": self.user.username, "email": "staff@example.invalid",
            "is_staff": "on", "date_joined_0": self.user.date_joined.strftime("%Y-%m-%d"),
            "date_joined_1": self.user.date_joined.strftime("%H:%M:%S"), "_save": "Save",
        }
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.client.post(url, {**data, "is_active": "on"}).status_code, 302)
        self.assertFalse(self.signed_in())

    def test_registry_event_filter_allows_status_update_on_the_assigned_operator(self):
        event = Event.objects.create(name_rus="Fixture", event_code="SR", date_start=date.today(), date_end=date.today())
        self.operator.events.add(event)
        url = reverse("operator-deactivate", args=[self.operator.pk])
        self.assertEqual(self.client.post(f"{url}?event_id={event.pk}").status_code, 200)
        self.assertTrue(UserSessionGeneration.objects.filter(user=self.user).exists())


class SessionGenerationMigrationTests(TransactionTestCase):
    def test_existing_inactive_and_previously_deactivated_users_start_with_a_revocation(self):
        previous = ("eventproject", "0024_recompute_is_resident")
        latest = ("eventproject", "0025_user_session_generation")
        executor = MigrationExecutor(connection)
        executor.migrate([previous])
        try:
            apps = executor.loader.project_state([previous]).apps
            account = apps.get_model("auth", "User")
            profile = apps.get_model("eventproject", "Operator")
            history = apps.get_model("eventproject", "OperatorAccessEvent")
            ordinary = account.objects.create(username="uninterrupted")
            inactive = account.objects.create(username="inactive", is_active=False)
            reactivated = account.objects.create(username="reactivated")
            historical = profile.objects.create(user=reactivated)
            history.objects.create(operator=historical, event_type="deactivated")
            history.objects.create(operator=historical, event_type="deactivated")
        finally:
            MigrationExecutor(connection).migrate([latest])
            self.addCleanup(_migrate_to_latest)
        markers = dict(UserSessionGeneration.objects.values_list("user_id", "generation"))
        self.assertNotIn(ordinary.pk, markers)
        self.assertEqual(markers[inactive.pk], 1)
        self.assertEqual(markers[reactivated.pk], 1)
