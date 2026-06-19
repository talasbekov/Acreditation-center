from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from eventproject.models import Operator, Event
from eventproject.permissions import IsOperator, IsSuperoperator, IsSuperuser
from eventproject.serializers.rbac import get_operator_events


def _make_request(user):
    """Build a minimal mock request with the given user."""
    req = MagicMock()
    req.user = user
    return req


class RolePropertyTest(TestCase):
    def setUp(self):
        self.su_user = User.objects.create_user("su_rbac", is_superuser=True)

        self.sop_user = User.objects.create_user("sop_rbac")
        Operator.objects.create(
            user=self.sop_user,
            patronymic="Sop",
            phone_number="+70000000001",
            workplace="HQ",
            role="superoperator",
        )

        self.op_user = User.objects.create_user("op_rbac")
        Operator.objects.create(
            user=self.op_user,
            patronymic="Op",
            phone_number="+70000000002",
            workplace="HQ",
            role="operator",
        )

    def test_operator_role_property(self):
        self.assertEqual(self.op_user.role, "operator")

    def test_superuser_role_property(self):
        self.assertEqual(self.su_user.role, "superuser")

    def test_superoperator_role_property(self):
        self.assertEqual(self.sop_user.role, "superoperator")


class PermissionClassTest(TestCase):
    def _user_with_role(self, role, is_superuser=False):
        user = MagicMock()
        user.is_authenticated = True
        user.is_superuser = is_superuser
        user.role = role
        return user

    def test_is_superoperator_permission_allows_superoperator(self):
        perm = IsSuperoperator()
        request = _make_request(self._user_with_role("superoperator"))
        self.assertTrue(perm.has_permission(request, None))

    def test_is_superoperator_permission_blocks_operator(self):
        perm = IsSuperoperator()
        request = _make_request(self._user_with_role("operator"))
        self.assertFalse(perm.has_permission(request, None))

    def test_is_operator_permission_allows_all_elevated_roles(self):
        perm = IsOperator()
        for role in ("operator", "superoperator", "superuser"):
            request = _make_request(self._user_with_role(role))
            self.assertTrue(perm.has_permission(request, None), f"Expected True for role={role}")


class RbacCheckEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("rbac_ep_user", password="pass")
        Operator.objects.create(
            user=self.user,
            patronymic="EP",
            phone_number="+70000000099",
            workplace="HQ",
            role="operator",
        )

    def test_rbac_check_returns_role(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/rbac-check/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "operator")

    def test_rbac_check_unauthenticated_returns_403(self):
        response = self.client.get("/api/v1/rbac-check/")
        self.assertIn(response.status_code, (401, 403))


class GetOperatorEventsTest(TestCase):
    def setUp(self):
        self.event1 = Event.objects.create(
            name_rus="Event 1",
            name_kaz="Event 1",
            name_eng="Event 1",
            event_code="E1",
            date_start="2026-01-01",
            date_end="2026-01-02",
            city_code="AK",
        )
        self.event2 = Event.objects.create(
            name_rus="Event 2",
            name_kaz="Event 2",
            name_eng="Event 2",
            event_code="E2",
            date_start="2026-02-01",
            date_end="2026-02-02",
            city_code="AK",
        )
        self.op_user = User.objects.create_user("op_events_rbac")
        self.op = Operator.objects.create(
            user=self.op_user,
            patronymic="Op",
            phone_number="+70000000003",
            workplace="HQ",
            role="operator",
        )
        self.op.events.add(self.event1)

        self.sop_user = User.objects.create_user("sop_events_rbac")
        Operator.objects.create(
            user=self.sop_user,
            patronymic="Sop",
            phone_number="+70000000004",
            workplace="HQ",
            role="superoperator",
        )

    def test_operator_sees_only_own_events(self):
        qs = get_operator_events(self.op_user)
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.event1.id, ids)
        self.assertNotIn(self.event2.id, ids)

    def test_superoperator_sees_all_events(self):
        qs = get_operator_events(self.sop_user)
        ids = list(qs.values_list("id", flat=True))
        self.assertIn(self.event1.id, ids)
        self.assertIn(self.event2.id, ids)
