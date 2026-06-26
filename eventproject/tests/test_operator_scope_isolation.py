"""Story hd-5.3: централизованный scope-резолвер — per-узел изоляция операторов."""
from rest_framework.test import APIClient

from django.test import TestCase

from eventproject.models import Category, Event
from eventproject.serializers.rbac import get_operator_attendee_queryset
from eventproject.tests.test_attendee_api import (
    _make_attendee,
    _make_operator,
    _make_request,
)


class OperatorScopeIsolationTests(TestCase):
    """AC-3/AC-4: оператор листа A не видит sibling B / parent-aggregate / чужое."""

    def setUp(self):
        # Иерархия hd-5.1: контейнер P → листья A, B.
        self.parent = Event.objects.create(
            name_rus="P", name_kaz="P", name_eng="P", title="Big", is_container=True
        )
        self.a = Event.objects.create(name_rus="A", title="Leaf A", parent=self.parent)
        self.b = Event.objects.create(name_rus="B", title="Leaf B", parent=self.parent)

        self.opA_user, self.opA = _make_operator("opA", "operator", event=self.a)
        self.opB_user, self.opB = _make_operator("opB", "operator", event=self.b)
        self.su_user, self.su = _make_operator("su", "superoperator")

        self.reqA = _make_request(self.a, self.opA)
        self.reqB = _make_request(self.b, self.opB)
        # Однофамилец в чужом под-событии — изоляция должна держаться структурой.
        self.attA = _make_attendee(self.reqA, surname="Однофамилец")
        self.attB = _make_attendee(self.reqB, surname="Однофамилец")

    def test_operator_sees_only_own_leaf(self):
        qs = get_operator_attendee_queryset(self.opA_user)
        ids = set(qs.values_list("id", flat=True))
        self.assertEqual(ids, {self.attA.id})           # только A
        self.assertNotIn(self.attB.id, ids)             # НЕ sibling B

    def test_operator_does_not_see_parent_aggregate(self):
        # opA привязан к листу A, НЕ к контейнеру P — не должен видеть roll-up.
        qs = get_operator_attendee_queryset(self.opA_user)
        # участник B (другой лист того же big-event) не виден через parent
        self.assertNotIn(self.attB.id, set(qs.values_list("id", flat=True)))

    def test_superoperator_sees_all_leaves(self):
        qs = get_operator_attendee_queryset(self.su_user)
        ids = set(qs.values_list("id", flat=True))
        self.assertIn(self.attA.id, ids)
        self.assertIn(self.attB.id, ids)               # aggregate видит супероператор

    def test_detail_foreign_id_returns_404_not_leak(self):
        client = APIClient()
        client.force_authenticate(self.opA_user)
        # opA запрашивает участника из чужого листа B → 404 (не 200/leak)
        resp = client.get(f"/api/v1/attendees/{self.attB.id}/")
        self.assertEqual(resp.status_code, 404)
        # свой — 200
        resp_own = client.get(f"/api/v1/attendees/{self.attA.id}/")
        self.assertEqual(resp_own.status_code, 200)

    def test_foreign_tree_isolation(self):
        """AC-4 (review-патч): оператор НЕ видит участника из ДРУГОГО big-event."""
        far_parent = Event.objects.create(
            name_rus="Q", name_kaz="Q", name_eng="Q", title="Other Big",
            is_container=True,
        )
        far_leaf = Event.objects.create(name_rus="C", title="Leaf C", parent=far_parent)
        _opC_user, opC = _make_operator("opC", "operator", event=far_leaf)
        reqC = _make_request(far_leaf, opC)
        attC = _make_attendee(reqC, surname="Чужедрев")

        qs = get_operator_attendee_queryset(self.opA_user)
        self.assertNotIn(attC.id, set(qs.values_list("id", flat=True)))  # list-изоляция

        client = APIClient()
        client.force_authenticate(self.opA_user)
        self.assertEqual(  # detail чужого дерева → 404, не leak
            client.get(f"/api/v1/attendees/{attC.id}/").status_code, 404
        )


class OperatorCategoryAndSemanticsTests(TestCase):
    """AC-2: events ∩ category (AND) — при заданной Operator.category."""

    def setUp(self):
        self.event = Event.objects.create(name_rus="E", title="E")
        self.cat_vip = Category.objects.create(event=self.event, name="VIP")
        self.cat_press = Category.objects.create(event=self.event, name="Press")
        self.op_user, self.op = _make_operator("opcat", "operator", event=self.event)
        self.req = _make_request(self.event, self.op)
        self.att_vip = _make_attendee(self.req, category=self.cat_vip)
        self.att_press = _make_attendee(self.req, category=self.cat_press)

    def test_no_category_sees_all_in_event(self):
        # Operator.category=NULL → сужение только по событию.
        qs = get_operator_attendee_queryset(self.op_user)
        ids = set(qs.values_list("id", flat=True))
        self.assertEqual(ids, {self.att_vip.id, self.att_press.id})

    def test_category_narrows_to_intersection(self):
        # Operator.category=VIP → видит ТОЛЬКО VIP (events ∩ category).
        self.op.category = self.cat_vip
        self.op.save(update_fields=["category"])
        qs = get_operator_attendee_queryset(self.op_user)
        ids = set(qs.values_list("id", flat=True))
        self.assertEqual(ids, {self.att_vip.id})
        self.assertNotIn(self.att_press.id, ids)

    def test_foreign_category_detail_returns_404_not_leak(self):
        """AC-4 (review-патч): detail участника ЧУЖОЙ категории → 404 (не leak)."""
        self.op.category = self.cat_vip
        self.op.save(update_fields=["category"])
        client = APIClient()
        client.force_authenticate(self.op_user)
        # Press вне category-scope оператора (VIP) → 404, даже своё событие
        self.assertEqual(
            client.get(f"/api/v1/attendees/{self.att_press.id}/").status_code, 404
        )
        # VIP — своё → 200
        self.assertEqual(
            client.get(f"/api/v1/attendees/{self.att_vip.id}/").status_code, 200
        )


class OperatorScopeFailClosedTests(TestCase):
    """AC-1: fail-closed для anon / без Operator."""

    def test_anonymous_empty(self):
        from django.contrib.auth.models import AnonymousUser

        qs = get_operator_attendee_queryset(AnonymousUser())
        self.assertEqual(qs.count(), 0)

    def test_user_without_operator_empty(self):
        from django.contrib.auth.models import User

        u = User.objects.create_user(username="noop", password="StrongPass123!")
        qs = get_operator_attendee_queryset(u)
        self.assertEqual(qs.count(), 0)
