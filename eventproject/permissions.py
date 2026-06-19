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
