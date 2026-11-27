from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import NoReverseMatch, resolve, reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from eventproject.models import Attendee, Event, Operator, Request
from eventproject.serializers.operator import (
    OperatorReadSerializer, OperatorRegistryListSerializer, OperatorRegistryDetailSerializer,
)
from eventproject.views.operator_api import OperatorViewSet


class OperationPolicyTests(TestCase):
    def test_superuser_privilege_requires_the_admin_flag(self):
        profile_user = User.objects.create_user("old-profile")
        Operator.objects.create(user=profile_user, role="superuser")
        self.assertEqual(profile_user.role, "user")
        profile_user.is_superuser = True
        self.assertEqual(profile_user.role, "superuser")

    def test_only_admin_can_edit_profile_role_or_reassign_existing_profile(self):
        from django.contrib import admin
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        request.user = User.objects.create_user("delegated-editor", is_staff=True)
        profile = Operator.objects.create(user=User.objects.create_user("profile"))
        registry = admin.site._registry[Operator]
        self.assertTrue({"role", "user", "is_accreditator"} <= set(registry.get_readonly_fields(request, profile)))
        request.user.is_superuser = True
        self.assertNotIn("role", registry.get_readonly_fields(request, profile))


    def test_bulk_cleanup_has_no_published_route(self):
        with self.assertRaises(NoReverseMatch):
            reverse("flush_outdated_events")

    def test_registry_detail_only_advertises_reads(self):
        route = resolve(reverse("operator-detail", args=[1]))
        self.assertEqual(set(route.func.actions) - {"head"}, {"get"})

    def test_response_serializers_have_no_writable_fields(self):
        for cls in (OperatorReadSerializer, OperatorRegistryListSerializer, OperatorRegistryDetailSerializer):
            with self.subTest(serializer=cls.__name__):
                self.assertEqual([f.field_name for f in cls().fields.values() if not f.read_only], [])

    def test_delegated_credential_and_activation_actions_are_limited_to_ordinary_accounts(self):
        # Evaluate object-permission policy directly, without executing account operations.
        actor = User.objects.create_user("delegated")
        Operator.objects.create(user=actor, role="superoperator")
        target = Operator.objects.create(user=User.objects.create_user("ordinary"), role="operator")
        peer = Operator.objects.create(user=User.objects.create_user("peer"), role="superoperator")
        staff = Operator.objects.create(user=User.objects.create_user("staff", is_staff=True))
        admin = Operator.objects.create(user=User.objects.create_user("admin", is_superuser=True))
        accreditor = Operator.objects.create(user=User.objects.create_user("accreditor"), is_accreditator=True)
        for action in ("reactivate", "resend_credentials"):
            view = OperatorViewSet()
            view.action_map = {"post": action}
            request = APIRequestFactory().post("/")
            force_authenticate(request, user=actor)
            view.request = view.initialize_request(request)
            view.action = action
            for obj, allowed in ((target, True), (peer, False), (staff, False), (admin, False), (accreditor, False)):
                with self.subTest(action=action, role=obj.user.username):
                    self.assertEqual(all(p.has_object_permission(view.request, view, obj)
                                         for p in view.get_permissions()), allowed)


class LocalizedEventAssignmentTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("assigned")
        self.operator = Operator.objects.create(user=user)
        self.event = Event.objects.create(
            name_rus="Fixture", name_eng="Fixture", name_kaz="Fixture", event_code="FIX",
            date_start=date.today(), date_end=date.today() + timedelta(days=1), city_code="AK",
        )
        self.operator.events.add(self.event)
        self.req = Request.objects.create(name="Assigned", event=self.event, status="Active",
                                          created_by=self.operator, registration_time=timezone.now())
        self.client.force_login(user)

    def test_current_assignment_controls_operator_list_and_detail_in_all_languages(self):
        for prefix in ("", "/en", "/kz"):
            self.assertEqual(self.client.get(f"{prefix}/show/{self.req.pk}/").status_code, 200)
            self.assertIn(self.req, self.client.get(f"{prefix}/application/").context["reqs"])
        self.operator.events.remove(self.event)
        for prefix in ("", "/en", "/kz"):
            with self.subTest(prefix=prefix):
                self.assertNotIn(self.req, self.client.get(f"{prefix}/application/").context["reqs"])
                self.assertEqual(self.client.get(f"{prefix}/show/{self.req.pk}/").status_code, 404)

    def test_administrator_unbinds_an_event_by_submitting_the_operator_form(self):
        admin_user = User.objects.create_superuser("assignment-admin", email="test@example.invalid")
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(admin_user)
        operator_page = browser.get(f"/show_operator/{self.operator.pk}/")
        url = f"/unbind_event/{self.event.pk}/{self.operator.user.username}/"
        self.assertContains(operator_page, f'action="{url}"')
        self.assertEqual(browser.get(url).status_code, 405)
        self.assertEqual(browser.post(url).status_code, 403)
        self.assertTrue(self.operator.events.filter(pk=self.event.pk).exists())
        response = browser.post(url, {"csrfmiddlewaretoken": browser.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.operator.events.filter(pk=self.event.pk).exists())

    def test_stale_event_selection_is_rechecked_before_creating_a_request(self):
        self.operator.events.remove(self.event)
        for prefix in ("", "/en", "/kz"):
            with self.subTest(prefix=prefix):
                response = self.client.post(f"{prefix}/create/{self.event.pk}/")
                self.assertEqual(response.status_code, 404)
        self.assertEqual(Request.objects.filter(event=self.event).count(), 1)

    def test_localized_request_workflow_uses_csrf_protected_posts(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.operator.user)
        for prefix in ("", "/en", "/kz"):
            with self.subTest(prefix=prefix):
                browser.get(f"{prefix}/application/")
                token = browser.cookies["csrftoken"].value
                url = f"{prefix}/create/{self.event.pk}/"
                self.assertEqual(browser.get(url).status_code, 405)
                self.assertEqual(browser.post(url).status_code, 403)
                response = browser.post(url, {"csrfmiddlewaretoken": token})
                self.assertEqual(response.status_code, 200)
                created = response.context["req"]
                # Этап C: пустую заявку отправить нельзя; участник должен быть полным.
                member = Attendee.objects.create(
                    surname="Тест", firstname="Имя", post="P", countryId="1000000840", is_resident=False,
                    docTypeId="passport", docSeries="AA", docIssue="МВД", sexId="M", visitObjects="Зал",
                    transcription="T", request=created, dateAdd=timezone.now(), photo="p.jpg", docScan="d.jpg",
                )
                # Предпросмотр — только чтение (этап C): GET открывает его без смены статуса.
                preview_url = f"{prefix}/preview/{created.pk}/"
                self.assertEqual(browser.get(preview_url).status_code, 200)
                self.assertEqual(browser.post(preview_url).status_code, 403)
                created.refresh_from_db()
                self.assertEqual(created.status, "Active")
                for action, code in (("back_to_change", 302), ("send", 200)):
                    url = f"{prefix}/{action}/{created.pk}/"
                    self.assertEqual(browser.get(url).status_code, 405)
                    self.assertEqual(browser.post(url, {"csrfmiddlewaretoken": token}).status_code, code)
                created.refresh_from_db()
                self.assertEqual(created.status, "Sent")
                member.refresh_from_db()
                self.assertEqual(member.status, "submitted")

    def test_bulk_event_removal_is_unavailable_in_admin(self):
        from django.contrib import admin
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser("admin-fixture", email="admin@example.invalid")
        self.assertNotIn("delete_selected", admin.site._registry[Event].get_actions(request))


class EventDeletionFailureTests(TestCase):
    def test_storage_error_keeps_event_for_retry(self):
        from unittest.mock import patch

        user = User.objects.create(username="synthetic-cleanup", is_superuser=True)
        item = Event.objects.create(name_rus="Synthetic")
        self.client.force_login(user)
        with patch("eventproject.views.event.shutil.rmtree", side_effect=OSError("synthetic")):
            response = self.client.post(reverse("delete_event", args=[item.pk]))
        self.assertEqual(response.status_code, 503)
        self.assertTrue(Event.objects.filter(pk=item.pk).exists())
