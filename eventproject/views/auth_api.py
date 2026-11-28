"""Вход, выход, профиль и смена пароля для интерфейса на Next.js.

Поведение повторяет HTML-вьюхи `user_login`, `user_logout` и `change_password`
(views/views.py): та же блокировка axes, то же сообщение про деактивированный
аккаунт, тот же аудит и та же история доступа оператора. Отличие одно: вместо
редиректа и шаблона — JSON с машинным кодом ошибки (`type`), текст по коду
рисует фронтенд.

Все мутации защищены CSRF: DRF проверяет CSRF только у уже вошедшего
пользователя, поэтому вход отдельно обёрнут в `csrf_protect`.
"""

import logging

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from eventproject.audit import audit_log
from eventproject.services.access_events import record_access_event

logger = logging.getLogger("eventproject")


def _error(code, http_status, field=None):
    """Ответ в формате RFC 7807, как у `rfc7807_exception_handler`."""
    from eventproject.errors.registry import spec_for

    spec = spec_for(code)
    body = {"type": code, "field": field, "params": {}, "detail": spec["detail"]}
    if field:
        body["errors"] = {field: spec["detail"]}
    return Response(body, status=http_status)


def user_payload(user):
    """Кто вошёл: роль, ФИО и признак обязательной смены пароля."""
    operator = getattr(user, "operator", None)
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
        "is_superuser": user.is_superuser,
        "operator_id": operator.id if operator is not None else None,
        "patronymic": operator.patronymic if operator is not None else "",
        "workplace": operator.workplace if operator is not None else "",
        "force_password_change": bool(
            operator is not None and not user.is_superuser and operator.force_password_change
        ),
    }


def _client_ip(request):
    return request.META.get("REMOTE_ADDR", "")


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get("username", ""))
        password = str(request.data.get("password", ""))

        from axes.handlers.proxy import AxesProxyHandler

        if AxesProxyHandler.is_locked(request, {"username": username}):
            return _error("login_locked", status.HTTP_429_TOO_MANY_REQUESTS)

        user = authenticate(request, username=username, password=password)
        if user is None:
            # Как в HTML-вьюхе: ModelBackend не пускает неактивных, поэтому
            # деактивированный аккаунт отличаем отдельной проверкой.
            if User.objects.filter(username=username, is_active=False).exists():
                return _error("account_disabled", status.HTTP_403_FORBIDDEN)
            return _error("login_bad", status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return _error("account_disabled", status.HTTP_403_FORBIDDEN)

        login(request, user)
        operator = getattr(user, "operator", None)
        try:
            ip = _client_ip(request)
            audit_log(user=user, action="user.login", obj_type="User", obj_id=user.id, ip=ip)
            if operator is not None:
                record_access_event(operator, "login", actor=user, ip=ip)
        except Exception:
            logger.error("failed to record login access event")
        return Response(user_payload(user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_payload(request.user))


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = str(request.data.get("old_password", ""))
        new_password = str(request.data.get("new_password", ""))
        new_password_repeat = str(request.data.get("new_password_repeat", ""))
        user = request.user

        if not new_password or new_password != new_password_repeat:
            return _error("pw_mismatch", status.HTTP_400_BAD_REQUEST, field="new_password_repeat")
        if not user.check_password(old_password):
            return _error("pw_wrong_old", status.HTTP_400_BAD_REQUEST, field="old_password")
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            body = {
                "type": "pw_weak",
                "field": "new_password",
                "params": {},
                "detail": " ".join(exc.messages),
                "errors": {"new_password": " ".join(exc.messages)},
            }
            return Response(body, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)
        operator = getattr(user, "operator", None)
        if operator is not None and operator.force_password_change:
            operator.force_password_change = False
            operator.save(update_fields=["force_password_change"])
        try:
            ip = _client_ip(request)
            audit_log(user=user, action="user.change_password", obj_type="User", obj_id=user.id, ip=ip)
            if operator is not None:
                record_access_event(operator, "password_changed", actor=user, ip=ip)
        except Exception:
            logger.error("failed to record password_changed event")
        return Response(user_payload(user))
