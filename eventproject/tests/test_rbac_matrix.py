"""Story hd-7.1 — data-driven RBAC-харнесс: читает oracle (rbac_matrix.py), сверяет
фактический ответ КАЖДОГО защищённого эндпоинта с ожидаемым.

История ТЕСТ+ДОК: рантайм-authz (резолвер/permissions/модели) НЕ меняется. Тесты
ДОКАЗЫВАЮТ изоляцию, уже реализованную в hd-5.1 (иерархия) и hd-5.3 (scope-резолвер).

Каждая ячейка oracle → отдельный сгенерированный тест-метод (не subTest): счётчик
сюита растёт по-ячеечно, падение локализуется до конкретной (actor, endpoint, action).

Топология фикстур (оператор A привязан к листу A, категория cat_own):
    контейнер P ─┬─ лист A  (opA, cat_own | cat_foreign)
                 └─ лист B  (sibling, opB)
    контейнер Q ─── лист C  (foreign-tree, opC)
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase

from eventproject.models import Category, Event
from eventproject.state_machine import AttendeeStatus
from eventproject.tests import rbac_matrix as M
from eventproject.tests.rbac_matrix import (
    ACTIONS,
    EXCLUDED,
    INCLUDED,
    ROLE_GATE,
    ROLE_GATE_ENDPOINTS,
    STATUS_OUTCOMES,
)
from eventproject.tests.test_attendee_api import (
    CREATE_BDATE,
    CREATE_IIN,
    KZ,
    OTHER,
    _make_attendee,
    _make_operator,
    _make_request,
)
from rest_framework.test import APIClient


class RBACMatrixBase(TestCase):
    """Общая иерархия + реестры фикстур для всех data-driven прогонов."""

    def setUp(self):
        # ── Иерархия (hd-5.1): два больших события (контейнера) ──
        self.P = Event.objects.create(
            name_rus="P", name_kaz="P", name_eng="P", title="Big P", is_container=True
        )
        self.A = Event.objects.create(name_rus="A", title="Leaf A", parent=self.P)
        self.B = Event.objects.create(name_rus="B", title="Leaf B", parent=self.P)
        self.Q = Event.objects.create(
            name_rus="Q", name_kaz="Q", name_eng="Q", title="Big Q", is_container=True
        )
        self.C = Event.objects.create(name_rus="C", title="Leaf C", parent=self.Q)

        # ── Категории листа A: своя оператора + чужая ──
        self.cat_own = Category.objects.create(event=self.A, name="OwnCat")
        self.cat_foreign = Category.objects.create(event=self.A, name="ForeignCat")

        # ── Акторы ──
        self.opA_user, self.opA = _make_operator("hd71_opA", "operator", event=self.A)
        self.opA.category = self.cat_own
        self.opA.save(update_fields=["category"])
        self.opB_user, self.opB = _make_operator("hd71_opB", "operator", event=self.B)
        self.opC_user, self.opC = _make_operator("hd71_opC", "operator", event=self.C)
        self.soper_user, self.soper = _make_operator("hd71_soper", "superoperator")
        self.su_user = User.objects.create_superuser(
            "hd71_su", "su@example.kz", "StrongPass123!"
        )
        self.plain_user = User.objects.create_user(
            "hd71_user", password="StrongPass123!"
        )  # User без Operator → role == "user"

        # ── Заявки (по одной на лист) ──
        self.reqA = _make_request(self.A, self.opA)
        self.reqB = _make_request(self.B, self.opB)
        self.reqC = _make_request(self.C, self.opC)

        # ── Участники (все «чужие» СУЩЕСТВУЮТ; negative-цели draft) ──
        # attA — единственный VALID_IIN в событии A (дедуп не конфликтует с iin=None).
        self.attA = _make_attendee(self.reqA, category=self.cat_own, surname="Свой")
        self.attA_fcat = _make_attendee(
            self.reqA, category=self.cat_foreign, surname="ЧужаяКат",
            iin=None, countryId=OTHER, is_resident=False,
        )
        self.attA_locked = _make_attendee(
            self.reqA, category=self.cat_own, surname="Locked",
            iin=None, status=AttendeeStatus.READY,
        )
        self.attB = _make_attendee(self.reqB, surname="Сосед")
        self.attC = _make_attendee(self.reqC, surname="Чужедрев")

        # ── Реестры: target-ключ → объект ──
        self._att = {
            "own": self.attA,
            "own_foreign_cat": self.attA_fcat,
            "own_locked": self.attA_locked,
            "sibling": self.attB,
            "foreign_tree": self.attC,
        }
        self._req = {
            "own": self.reqA,
            "own_foreign_cat": self.reqA,
            "own_locked": self.reqA,
            "sibling": self.reqB,
            "foreign_tree": self.reqC,
        }
        self._role_user = {
            "superuser": self.su_user,
            "superoperator": self.soper_user,
            "operator": self.opA_user,
            "user": self.plain_user,
            "anonymous": None,
        }

        # Клиент оператора A — субъект всех негативов AC-2.
        self.client = APIClient()
        self.client.force_authenticate(self.opA_user)

    # ── низкоуровневые помощники ──────────────────────────────────────────
    def _call(self, client, method, url, body=None, is_drf=True):
        method = method.lower()
        if method == "get":
            return client.get(url)
        if method == "delete":
            return client.delete(url)
        if is_drf:
            return getattr(client, method)(url, body or {}, format="json")
        return getattr(client, method)(url, body or {})

    def _body(self, kind, target):
        if kind == "patch":
            return {"post": "Изменено-тестом"}
        if kind == "reassign":
            return {"request": self._req[target].id}
        if kind == "create":
            body = dict(
                surname="Иванов", firstname="Иван", post="Менеджер", countryId=KZ,
                docTypeId="ID", docSeries="AB", docIssue="МВД", sexId="M",
                visitObjects="Зал A", transcription="Ivanov Ivan",
                birthDate=CREATE_BDATE, iin=CREATE_IIN, request=self._req[target].id,
            )
            if target == "own":
                body["category"] = self.cat_own.id
            return body
        return None

    def _result_ids(self, response):
        data = response.data
        results = data["results"] if isinstance(data, dict) and "results" in data else data
        return [row["id"] for row in results]

    def _assert_outcome(self, expected, response, target_id=None, msg=""):
        if expected in STATUS_OUTCOMES:
            body = getattr(response, "data", None)
            if body is None:
                body = getattr(response, "content", b"")
            self.assertEqual(
                response.status_code, int(expected),
                f"{msg}: ожидался {expected}, получен {response.status_code}; "
                f"body={str(body)[:200]}",
            )
        elif expected == EXCLUDED:
            ids = self._result_ids(response)
            self.assertNotIn(
                target_id, ids, f"{msg}: id={target_id} НЕ должен быть в выборке {ids}"
            )
        elif expected == INCLUDED:
            self.assertEqual(response.status_code, 200, f"{msg}: list ожидался 200")
            ids = self._result_ids(response)
            self.assertIn(
                target_id, ids, f"{msg}: id={target_id} должен быть в выборке {ids}"
            )
        else:  # pragma: no cover — защита от опечатки в oracle
            self.fail(f"{msg}: неизвестный outcome {expected!r}")

    # ── исполнители ───────────────────────────────────────────────────────
    def _run_operator_cell(self, cell):
        """Оператор A выполняет (action, target); сверка с oracle-кодом."""
        action, target, expected = cell["action"], cell["target"], cell["expected"]
        spec = ACTIONS[action]
        # fail-loud: target обязан резолвиться в фикстуру (прямой индекс, не .get):
        # пустой id из .get()+getattr дал бы /attendees// → 404 и ложно-зелёный кейс.
        att = self._att[target]
        req = self._req[target]
        url = spec["url"].format(att=att.id, req=req.id, own=self.attA.id)
        resp = self._call(self.client, spec["method"], url, self._body(spec.get("body"), target))
        list_target = spec.get("list_target")
        target_id = att.id if list_target == "att" else (req.id if list_target == "req" else None)
        label = cell.get("n", cell.get("name"))
        self._assert_outcome(expected, resp, target_id, msg=f"#{label} {action}/{target}")

    def _exec_role_gate(self, role, endpoint):
        spec = ROLE_GATE_ENDPOINTS[endpoint]
        url = spec["url"].format(ev=self.A.id, req=self.reqA.id)
        user = self._role_user[role]
        if spec["is_drf"]:
            client = APIClient()
            if user is not None:
                client.force_authenticate(user)
        else:
            client = Client(enforce_csrf_checks=False)
            if user is not None:
                client.force_login(user)
        return self._call(client, spec["method"], url, body={}, is_drf=spec["is_drf"])


class RBACMatrixOperatorTests(RBACMatrixBase):
    """AC-2: ~28 P0 негативов изоляции оператора + позитивные контроли.

    Тест-методы генерируются из oracle (P0_OPERATOR_CELLS + POSITIVE_CONTROLS) ниже.
    """

    def test_oracle_outcomes_are_valid(self):
        # Sanity: oracle не содержит опечаток в кодах исхода (ВСЕ структуры oracle).
        for cell in M.P0_OPERATOR_CELLS + M.POSITIVE_CONTROLS + M.MEDIA_CELLS:
            self.assertIn(cell["expected"], M.OUTCOMES, cell)
        for key, outcome in M.ROLE_GATE.items():
            self.assertIn(outcome, M.OUTCOMES, key)

    def test_gap_category_write_read_asymmetry(self):
        """Known gap (defer hd-5-2): write-side НЕ сужает по категории.

        Оператор СОЗДАЁТ участника с ЧУЖОЙ категорией в СВОЁМ событии (201,
        write-side), затем НЕ видит его (404, read-side сужает по категории).
        """
        body = self._body("create", "own")
        body["category"] = self.cat_foreign.id  # чужая категория в СВОЁМ событии
        resp = self.client.post("/api/v1/attendees/", body, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)  # write-side пропустил
        created_id = resp.data["id"]
        # read-side скрывает (category ≠ operator.category) → 404, НЕ 200/leak.
        self.assertEqual(
            self.client.get(f"/api/v1/attendees/{created_id}/").status_code, 404
        )


class RBACMatrixRoleGateTests(RBACMatrixBase):
    """AC-1/AC-2 (#26–30): role-gate матрица на КАЖДОМ защищённом эндпоинте."""

    def test_rolegate_coverage_complete(self):
        # Каждый role_gate-эндпоинт инвентаря представлен в ROLE_GATE oracle.
        gated = {e["key"] for e in M.ENDPOINTS if e["role_gate"]}
        covered = {ep for (_role, ep) in ROLE_GATE}
        self.assertEqual(gated - covered, set(), f"role-gate endpoints без oracle: {gated - covered}")
        # DRF role-gate эндпоинты обязаны покрывать ВСЕ роли (не только наличие ключа —
        # иначе пропуск (role × endpoint) ячейки проходит молча). Legacy (export/dashboard/
        # download_json) — denial-only по дизайну (success зависит от данных), не требуем.
        drf_endpoints = {k for k, s in ROLE_GATE_ENDPOINTS.items() if s["is_drf"]}
        for ep in drf_endpoints:
            roles = {role for (role, e) in ROLE_GATE if e == ep}
            self.assertEqual(
                set(M.ROLES), roles,
                f"DRF role-gate {ep}: не покрыты роли {set(M.ROLES) - roles}",
            )


# ── динамическая генерация тест-методов из oracle ──────────────────────────
def _make_operator_test(cell):
    def test(self):
        self._run_operator_cell(cell)

    label = cell.get("n", cell.get("name"))
    test.__doc__ = f"oracle #{label}: {cell['action']}({cell['target']}) → {cell['expected']}"
    return test


def _make_rolegate_test(role, endpoint, expected):
    def test(self):
        resp = self._exec_role_gate(role, endpoint)
        self._assert_outcome(expected, resp, msg=f"role-gate {role}/{endpoint}")

    test.__doc__ = f"role-gate {role} → {endpoint} → {expected}"
    return test


for _cell in M.P0_OPERATOR_CELLS:
    setattr(
        RBACMatrixOperatorTests,
        "test_p0_%02d_%s_%s" % (_cell["n"], _cell["action"], _cell["target"]),
        _make_operator_test(_cell),
    )

for _cell in M.POSITIVE_CONTROLS:
    setattr(
        RBACMatrixOperatorTests,
        "test_positive_%s" % _cell["name"],
        _make_operator_test(_cell),
    )

for (_role, _ep), _exp in ROLE_GATE.items():
    setattr(
        RBACMatrixRoleGateTests,
        "test_rolegate_%s_%s" % (_ep, _role),
        _make_rolegate_test(_role, _ep, _exp),
    )
