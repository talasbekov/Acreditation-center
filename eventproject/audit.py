import logging
import re

from eventproject.models import AuditLog
from eventproject.validators.iin import mask_iin

logger = logging.getLogger("eventproject")

# Story hd-4.2 (AC-1): реестр значимых действий — единственный источник правды
# для тест-чеклиста eventproject/tests/test_audit_action_coverage.py. Это НЕ enum
# БД-поля `AuditLog.action` (оно остаётся свободным CharField) — категоризация
# УЖЕ существующих action-строк по 6 категориям gap-анализа (вход / смена статуса /
# правки / экспорт / re-export / удаления). Имена action не переименовывались:
# они согласованы историей проекта (тесты/потребители логов).
SIGNIFICANT_ACTIONS = {
    "login": ["user.login"],
    "status_change": [
        "attendee.status_change", "attendee.approved", "attendee.returned",
    ],
    "edit": ["attendee.update", "attendee.iin_discarded", "user.change_password"],
    "export": [
        "export.download", "export.event_sent", "export.guests_sent",
        "export.guests_all", "export.request",
    ],
    # Функциональности re-export нет (зависит от hd-1-3, backlog) — категория
    # намеренно пуста: реестр фиксирует пробел явно, не имитирует его.
    "export.re_export": [],
    "delete": ["attendee.delete", "event.delete", "request.delete"],
}

# Story hd-4.1 (AC-4): defensive-сканер сырого ИИН (12 цифр) в extra. Call-sites
# обязаны маскировать сами (mask_iin), это страховочный слой — чтобы сырой ИИН
# не попал в durable-журнал даже при забытом маскировании.
_IIN_RE = re.compile(r"\b\d{12}\b")


def _scrub_pii(value):
    """Рекурсивно маскирует сырой 12-значный ИИН в значениях extra (str И int).

    Review hd-4.1 (AC-4): не только str-листья — `normalize_iin` принимает int,
    поэтому ИИН-int (`{"iin": 990101350511}`) тоже маскируем (→ str-маска),
    иначе сырой ИИН утёк бы в durable-журнал. bool исключён (подтип int).
    """
    if isinstance(value, str):
        return _IIN_RE.sub(lambda m: mask_iin(m.group()), value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        text = str(value)
        if _IIN_RE.search(text):
            return _IIN_RE.sub(lambda m: mask_iin(m.group()), text)
        return value
    if isinstance(value, dict):
        return {k: _scrub_pii(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub_pii(v) for v in value]
    return value


def _resolve_role(user) -> str:
    if not user:
        return "system"
    explicit_role = getattr(user, "role", None)
    if isinstance(explicit_role, str) and explicit_role:
        return explicit_role
    if getattr(user, "is_superuser", False):
        return "superuser"
    return "operator"


def audit_log(
    user,               # User instance или None (для Celery/unauthenticated)
    action: str,        # "attendee.create" | "attendee.update" | "attendee.delete" | ...
    obj_type: str,      # "Attendee" | "ExportLog" | "User" | ...
    obj_id,             # ID объекта (int или str, будет конвертирован в str)
    ip: str,            # request.META.get("REMOTE_ADDR") или "celery-worker"
    extra: dict = None, # дополнительный контекст (опционально)
) -> None:
    """Пишет audit-запись в durable DB-`AuditLog` (Story hd-4.1) И в stdout (зеркало).

    Синхронно, в текущей транзакции вызывающего view: при `transaction.atomic`
    (DRF perform_create/update/destroy) сбой DB-записи откатывает мутацию (AC-2).
    НЕ оборачивать в сигналы/Celery/on_commit — это вынесет запись за транзакцию.
    """
    role = _resolve_role(user)
    safe_extra = _scrub_pii(extra or {})

    # stdout-зеркало (NFR-5; structured JSON через console_json handler).
    logger.info(
        "audit",
        extra={
            "user_id": user.id if user else None,
            "role": role,
            "action": action,
            "obj_type": obj_type,
            "obj_id": str(obj_id),
            "ip": ip,
            "extra": safe_extra,
        },
    )

    # Durable append-only DB-запись (синхронно, в той же транзакции).
    # actor_id — снимок (НЕ FK): удаление User не трогает журнал.
    AuditLog.objects.create(
        actor_id=user.id if user else None,
        role=role,
        action=action,
        obj_type=obj_type,
        obj_id=str(obj_id),
        ip=ip,
        extra=safe_extra,
    )
