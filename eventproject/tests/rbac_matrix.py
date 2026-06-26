"""Story hd-7.1 — RBAC-матрица как МАШИННЫЙ oracle (единый источник истины).

Эти структуры данных читает data-driven харнесс ``test_rbac_matrix.py`` и
``test_rbac_bypass_paths.py``; их человекочитаемое зеркало — ``docs/rbac-matrix.md``.
Любое изменение ОЖИДАЕМОГО поведения RBAC правится ЗДЕСЬ и синхронно в docs
(FR-19: права «задокументированы И проверяются»). Это история-oracle: тесты НЕ
хардкодят коды инлайн — они читают ожидания отсюда.

ДВА enforcement-узла (НЕ смешивать — разные коды):
  • read-side  — ``get_operator_attendee_queryset`` / ``get_operator_events``
                 → доступ по **id** к чужому = **404** (объект вне выборки, не leak).
  • write-side — ``AttendeeSerializer.validate`` → ``get_operator_events``
                 → запись в **чужое событие** (create / reassign) = **403** PermissionDenied.

Граничные инварианты (anti-disaster, см. story Dev Notes):
  • detail чужого существующего ресурса = 404, НЕ пустой 200 (пустой = info-leak);
  • edit-lock (ready/exported → 403) маскирует 404 → negative-цели держим в ``draft``;
  • никакого upward-traversal: лист A ≠ доступ к siblings/контейнеру.
"""

# ── Коды исхода (oracle-словарь; харнесс транслирует в assert) ──────────────
OK = "200"             # доступ разрешён (retrieve / update / submit / list-200)
CREATED = "201"        # создание разрешено (write-side own-event)
FORBIDDEN = "403"      # role-gate (permission-класс) ИЛИ write-в-чужое (validate)
NOT_FOUND = "404"      # read-side queryset-изоляция: чужой id невидим
REDIRECT = "302"       # @user_passes_test / login_required → redirect на /user_login/
EXCLUDED = "excluded"  # list: id чужого НЕ в выборке (assertNotIn)
INCLUDED = "included"  # list: id своего В выборке (assertIn)

STATUS_OUTCOMES = {OK, CREATED, FORBIDDEN, NOT_FOUND, REDIRECT}
LIST_OUTCOMES = {EXCLUDED, INCLUDED}
OUTCOMES = STATUS_OUTCOMES | LIST_OUTCOMES

# ── Роли (User.role property — models.py:195-204) ──────────────────────────
ROLES = ("superuser", "superoperator", "operator", "user", "anonymous")

# ── Отношение целевого узла к оператору, привязанному к ЛИСТУ A ────────────
# (контейнер P; sibling B под P; чужое дерево — лист C под контейнером Q)
NODE_RELATIONS = (
    "own",              # лист A, СВОЯ категория оператора (позитивный контроль)
    "own_foreign_cat",  # участник в листе A, но category ≠ operator.category
    "own_locked",       # лист A, своя кат., статус ready/exported (edit-lock 403)
    "sibling",          # лист B (тот же контейнер P) — upward-роллапа нет
    "parent",           # контейнер P (нет прямых участников → семантика sibling)
    "foreign_tree",     # лист C (чужой контейнер Q)
)

# ── Инвентарь защищённых эндпоинтов (источник истины для «на КАЖДОМ») ───────
# scoped=True → данные сужаются резолвером; role_gate=True → доступ решается ролью.
ENDPOINTS = (
    {"key": "attendees",    "path": "/api/v1/attendees/",          "permission": "IsOperator",       "scoped": True,  "role_gate": True},
    {"key": "requests",     "path": "/api/v1/requests/",           "permission": "IsOperator",       "scoped": True,  "role_gate": True},
    {"key": "events",       "path": "/api/v1/events/",             "permission": "IsSuperoperator",  "scoped": False, "role_gate": True},
    {"key": "operators",    "path": "/api/v1/operators/",          "permission": "IsSuperoperator",  "scoped": False, "role_gate": True},
    {"key": "rbac_check",   "path": "/api/v1/rbac-check/",         "permission": "IsAuthenticated",  "scoped": False, "role_gate": True},
    {"key": "media",        "path": "/media/event_<id>/<file>",    "permission": "login+event-regex","scoped": True,  "role_gate": False},
    {"key": "export_delta", "path": "/export_delta/<ev>/<req>/",   "permission": "IsSuperoperator",  "scoped": False, "role_gate": True},
    {"key": "dashboard",    "path": "/dashboard/<ev>/",            "permission": "_is_superoperator","scoped": False, "role_gate": True},
    {"key": "download_json","path": "/download_json/<ev>/",        "permission": "is_superuser",     "scoped": False, "role_gate": True},
    {"key": "qr_success",   "path": "/qr/success/<pk>/",           "permission": "login+session",    "scoped": True,  "role_gate": False},
    {"key": "legacy_forms", "path": "/delete_request/<id>/ (+create/add_attendee/delete_attendee)", "permission": "login+ownership(created_by)", "scoped": True, "role_gate": False},
)

# ── Действия над участником/заявкой (url-template + method + тело) ──────────
# Харнесс подставляет id фикстур в {att}/{req}/{own}; тело собирает по `body`.
ACTIONS = {
    "retrieve":     {"method": "GET",    "url": "/api/v1/attendees/{att}/"},
    "update":       {"method": "PATCH",  "url": "/api/v1/attendees/{att}/", "body": "patch"},
    "delete":       {"method": "DELETE", "url": "/api/v1/attendees/{att}/"},
    "submit":       {"method": "POST",   "url": "/api/v1/attendees/{att}/submit/"},
    "reassign":     {"method": "PATCH",  "url": "/api/v1/attendees/{own}/", "body": "reassign"},
    "create":       {"method": "POST",   "url": "/api/v1/attendees/",       "body": "create"},
    "list":         {"method": "GET",    "url": "/api/v1/attendees/",       "list_target": "att"},
    "req_retrieve": {"method": "GET",    "url": "/api/v1/requests/{req}/"},
    "req_list":     {"method": "GET",    "url": "/api/v1/requests/",        "list_target": "req"},
}

# ════════════════════════════════════════════════════════════════════════════
# P0-перечисление #1–22 (оператор листа A, негативы + read/write коды разведены).
# Цели в статусе draft (иначе edit-lock 403 замаскирует 404). Все «чужие»
# участники СУЩЕСТВУЮТ — иначе тест не доказывает «не-leak».
# (#23–25 media — MEDIA_CELLS; #26–30 role-gate — ROLE_GATE.)
# ════════════════════════════════════════════════════════════════════════════
P0_OPERATOR_CELLS = (
    # retrieve по id → 404 (read-side queryset-изоляция)
    {"n": 1,  "action": "retrieve",     "target": "sibling",         "expected": NOT_FOUND},
    {"n": 2,  "action": "retrieve",     "target": "foreign_tree",    "expected": NOT_FOUND},
    {"n": 3,  "action": "retrieve",     "target": "own_foreign_cat", "expected": NOT_FOUND},
    # update по id → 404 (get_object перед edit-lock; цели draft)
    {"n": 4,  "action": "update",       "target": "sibling",         "expected": NOT_FOUND},
    {"n": 5,  "action": "update",       "target": "foreign_tree",    "expected": NOT_FOUND},
    {"n": 6,  "action": "update",       "target": "own_foreign_cat", "expected": NOT_FOUND},
    # reassign СВОЕГО участника на чужое событие → 403 (write-side validate)
    {"n": 7,  "action": "reassign",     "target": "sibling",         "expected": FORBIDDEN},
    {"n": 8,  "action": "reassign",     "target": "foreign_tree",    "expected": FORBIDDEN},
    # delete по id → 404
    {"n": 9,  "action": "delete",       "target": "sibling",         "expected": NOT_FOUND},
    {"n": 10, "action": "delete",       "target": "foreign_tree",    "expected": NOT_FOUND},
    {"n": 11, "action": "delete",       "target": "own_foreign_cat", "expected": NOT_FOUND},
    # submit по id → 404
    {"n": 12, "action": "submit",       "target": "sibling",         "expected": NOT_FOUND},
    {"n": 13, "action": "submit",       "target": "foreign_tree",    "expected": NOT_FOUND},
    # create с чужим request → 403 (write-side)
    {"n": 14, "action": "create",       "target": "sibling",         "expected": FORBIDDEN},
    {"n": 15, "action": "create",       "target": "foreign_tree",    "expected": FORBIDDEN},
    # list — исключение чужих из выборки
    {"n": 16, "action": "list",         "target": "sibling",         "expected": EXCLUDED},
    {"n": 17, "action": "list",         "target": "foreign_tree",    "expected": EXCLUDED},
    {"n": 18, "action": "list",         "target": "own_foreign_cat", "expected": EXCLUDED},
    # requests retrieve → 404
    {"n": 19, "action": "req_retrieve", "target": "sibling",         "expected": NOT_FOUND},
    {"n": 20, "action": "req_retrieve", "target": "foreign_tree",    "expected": NOT_FOUND},
    # requests list — исключение
    {"n": 21, "action": "req_list",     "target": "sibling",         "expected": EXCLUDED},
    {"n": 22, "action": "req_list",     "target": "foreign_tree",    "expected": EXCLUDED},
)

# ── Позитивные контроли (анти-over-block: изоляция ≠ «всё запретить») ───────
# own → доступ; own ready/exported update → 403 (edit-lock, НЕ 404).
POSITIVE_CONTROLS = (
    {"name": "own_retrieve",      "action": "retrieve", "target": "own",        "expected": OK},
    {"name": "own_update",        "action": "update",   "target": "own",        "expected": OK},  # own draft → 200 (не over-block)
    {"name": "own_list_included", "action": "list",     "target": "own",        "expected": INCLUDED},
    {"name": "own_create",        "action": "create",   "target": "own",        "expected": CREATED},
    {"name": "own_submit",        "action": "submit",   "target": "own",        "expected": OK},
    {"name": "own_req_retrieve",  "action": "req_retrieve", "target": "own",    "expected": OK},
    {"name": "own_locked_update", "action": "update",   "target": "own_locked", "expected": FORBIDDEN},  # edit-lock
)

# ════════════════════════════════════════════════════════════════════════════
# ROLE-GATE матрица: (role, endpoint) → outcome — «матрица на КАЖДОМ endpoint».
# DRF-эндпоинты покрыты для всех ролей; legacy (export/dashboard/download_json)
# — только denial-ячейки (operator/anon), success зависит от данных (см. docs).
# P0 #26–30 — подмножество (anon/user attendees-403; operator events/operators-403,
# download_json-302).
# ════════════════════════════════════════════════════════════════════════════
ROLE_GATE = {
    # attendees / requests: IsOperator (operator и выше — доступ; user/anon — 403)
    ("superuser",     "attendees"): OK,
    ("superoperator", "attendees"): OK,
    ("operator",      "attendees"): OK,
    ("user",          "attendees"): FORBIDDEN,   # P0 #27
    ("anonymous",     "attendees"): FORBIDDEN,   # P0 #26
    ("superuser",     "requests"):  OK,
    ("superoperator", "requests"):  OK,
    ("operator",      "requests"):  OK,
    ("user",          "requests"):  FORBIDDEN,
    ("anonymous",     "requests"):  FORBIDDEN,
    # events / operators: IsSuperoperator (operator/user/anon — 403)
    ("superuser",     "events"):    OK,
    ("superoperator", "events"):    OK,
    ("operator",      "events"):    FORBIDDEN,   # P0 #28
    ("user",          "events"):    FORBIDDEN,
    ("anonymous",     "events"):    FORBIDDEN,
    ("superuser",     "operators"): OK,
    ("superoperator", "operators"): OK,
    ("operator",      "operators"): FORBIDDEN,   # P0 #29
    ("user",          "operators"): FORBIDDEN,
    ("anonymous",     "operators"): FORBIDDEN,
    # rbac-check: IsAuthenticated (любой залогиненный — 200; anon — 403)
    ("superuser",     "rbac_check"): OK,
    ("superoperator", "rbac_check"): OK,
    ("operator",      "rbac_check"): OK,
    ("user",          "rbac_check"): OK,
    ("anonymous",     "rbac_check"): FORBIDDEN,
    # export_delta / dashboard: _is_superoperator (operator — 403; anon — 302 на логин)
    ("operator",      "export_delta"): FORBIDDEN,
    ("anonymous",     "export_delta"): REDIRECT,
    ("operator",      "dashboard"):    FORBIDDEN,
    ("anonymous",     "dashboard"):    REDIRECT,
    # legacy export: @user_passes_test(is_superuser) → не-су → 302 (gap-маркер)
    ("operator",      "download_json"): REDIRECT,  # P0 #30
    ("anonymous",     "download_json"): REDIRECT,
}

# ── Метаданные role-gate эндпоинтов для исполнителя (method + url-template) ──
# is_drf=True → APIClient.force_authenticate; иначе legacy Django Client.force_login.
# url с {ev}/{req} харнесс подставляет id своего события/заявки оператора.
ROLE_GATE_ENDPOINTS = {
    "attendees":    {"is_drf": True,  "method": "GET",  "url": "/api/v1/attendees/"},
    "requests":     {"is_drf": True,  "method": "GET",  "url": "/api/v1/requests/"},
    "events":       {"is_drf": True,  "method": "GET",  "url": "/api/v1/events/"},
    "operators":    {"is_drf": True,  "method": "GET",  "url": "/api/v1/operators/"},
    "rbac_check":   {"is_drf": True,  "method": "GET",  "url": "/api/v1/rbac-check/"},
    "export_delta": {"is_drf": False, "method": "POST", "url": "/export_delta/{ev}/{req}/"},
    "dashboard":    {"is_drf": False, "method": "GET",  "url": "/dashboard/{ev}/"},
    "download_json":{"is_drf": False, "method": "GET",  "url": "/download_json/{ev}/"},
}

# ════════════════════════════════════════════════════════════════════════════
# BYPASS-пути (в обход обычных DRF-вьюсетов) — P0 #23–25 (media) + QR.
# media: оператор листа A на event_{B|P|C}/ → 404; own event_{A}/ → 200.
# (Path-составляется харнессом: r"event_<id>/<file>" — см. protected_media.)
# ════════════════════════════════════════════════════════════════════════════
MEDIA_CELLS = (
    {"n": 23, "target": "sibling",      "expected": NOT_FOUND},  # event_{B}/
    {"n": 24, "target": "parent",       "expected": NOT_FOUND},  # event_{P}/
    {"n": 25, "target": "foreign_tree", "expected": NOT_FOUND},  # event_{C}/
    {"n": None, "target": "own",        "expected": OK},         # event_{A}/ (позитив)
)

# ── Known gaps → defer (зеркало раздела docs/rbac-matrix.md) ───────────────
# Слабые места, зафиксированные тестом-маркером (поведение НЕ чиним здесь — defer).
KNOWN_GAPS = (
    {
        "id": "legacy-export-no-event-scope",
        "where": "eventproject/views/file_download.py (download_json и др.)",
        "issue": "@user_passes_test(is_superuser) — без per-event scope; "
                 "прямой is_superuser в обход permission-классов (architecture.md:436).",
        "defer_to": "hd-1-* (Безопасный экспорт) / hd-5-5 (ExportLog per-leaf)",
    },
    {
        "id": "qr-success-no-event-scope",
        "where": "qr_event/views.py:68 qr_success_view",
        "issue": "доступ = (pk in session) OR is_superuser — без event-scope; "
                 "entrance/scan-валидации эндпоинта НЕТ (не выдумывать).",
        "defer_to": "новая QR-история",
    },
    {
        "id": "category-write-read-asymmetry",
        "where": "AttendeeSerializer.validate → get_operator_events (write-side)",
        "issue": "write-side НЕ сужает по категории → оператор создаёт участника с "
                 "чужой категорией в СВОЁМ событии (201), затем НЕ видит его "
                 "(read-side сужает по категории → 404).",
        "defer_to": "hd-5-2 (leaf-only / category enforcement)",
    },
)
