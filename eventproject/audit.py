import logging

logger = logging.getLogger("eventproject")


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
    logger.info(
        "audit",
        extra={
            "user_id": user.id if user else None,
            "role": _resolve_role(user),
            "action": action,
            "obj_type": obj_type,
            "obj_id": str(obj_id),
            "ip": ip,
            "extra": extra or {},
        },
    )
