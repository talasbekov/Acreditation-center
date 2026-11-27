from rest_framework.permissions import BasePermission


class IsSuperuser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "superuser"


class IsSuperoperator(BasePermission):
    """Супероператор ИЛИ Суперпользователь."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ("superoperator", "superuser")


class IsOperator(BasePermission):
    """Оператор, Супероператор или Суперпользователь."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ("operator", "superoperator", "superuser")


def can_manage_operator_account(actor, target):
    return actor.is_superuser or (
        target.role in ("operator", "user")
        and not target.user.is_superuser
        and not target.user.is_staff
        and not target.is_accreditator
    )


class OperatorRegistryPermission(IsSuperoperator):
    def has_object_permission(self, request, view, obj):
        if view.action in ("resend_credentials", "reactivate"):
            return can_manage_operator_account(request.user, obj)
        # Deactivation also has dedicated validation for self and administrator accounts.
        return view.action in ("retrieve", "deactivate")
