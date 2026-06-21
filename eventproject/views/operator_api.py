"""Story 2.3 — DRF API онбординга операторов (`/api/v1/operators/`).

Отдельный модуль от legacy `eventproject/views/operator.py` (function-based
`add_operator`), чтобы не ломать существующий Django-UI (Strangler Fig).
"""

import logging

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from eventproject.audit import audit_log
from eventproject.models import Operator
from eventproject.permissions import IsSuperoperator
from eventproject.serializers import (
    OperatorCreateSerializer,
    OperatorReadSerializer,
)
from eventproject.services.email import send_operator_credentials
from eventproject.services.operator_onboarding import (
    create_operator,
    generate_password,
)

logger = logging.getLogger("eventproject")


class OperatorViewSet(viewsets.ModelViewSet):
    """CRUD операторов для Супероператора/Суперпользователя.

    create: создаёт User+Operator с авто-генерацией credentials и шлёт email.
    resend_credentials: пересоздаёт пароль и повторно отправляет письмо.
    """

    permission_classes = [IsSuperoperator]
    serializer_class = OperatorReadSerializer

    def get_queryset(self):
        return Operator.objects.select_related("user").all()

    def get_serializer_class(self):
        if self.action == "create":
            return OperatorCreateSerializer
        return OperatorReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = OperatorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        operator, temporary_password = create_operator(serializer.validated_data)

        # Audit вызывается только из views (Dev Notes).
        audit_log(
            user=request.user,
            action="operator.create",
            obj_type="User",
            obj_id=operator.user.id,
            ip=request.META.get("REMOTE_ADDR", ""),
        )

        email_result = self._deliver_credentials(operator, temporary_password)

        body = OperatorReadSerializer(operator).data
        body["status"] = "email_error" if email_result == "error" else "created"
        return Response(body, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsSuperoperator])
    def resend_credentials(self, request, pk=None):
        operator = self.get_object()
        user = operator.user

        if not user.email:
            return Response(
                {"detail": "У оператора не указан email — отправка невозможна."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        temporary_password = generate_password()

        # КРИТИЧНО: сначала шлём письмо, и только при успехе ротируем пароль. Иначе
        # при недоступном SMTP старый (рабочий) пароль был бы уже уничтожен, а новый
        # не доставлен → оператор полностью заблокирован (review finding).
        email_result = self._deliver_credentials(operator, temporary_password)
        if email_result == "error":
            body = OperatorReadSerializer(operator).data
            body["status"] = "email_error"
            # Ничего не изменено: старый пароль остаётся рабочим. 502 — upstream SMTP.
            return Response(body, status=status.HTTP_502_BAD_GATEWAY)

        # Письмо доставлено → активируем новый пароль и форсируем его смену.
        user.set_password(temporary_password)
        user.save(update_fields=["password"])
        operator.force_password_change = True
        operator.save(update_fields=["force_password_change"])

        audit_log(
            user=request.user,
            action="operator.resend_email",
            obj_type="User",
            obj_id=user.id,
            ip=request.META.get("REMOTE_ADDR", ""),
        )

        body = OperatorReadSerializer(operator).data
        body["status"] = "resent"
        return Response(body, status=status.HTTP_200_OK)

    def _deliver_credentials(self, operator, temporary_password):
        """Отправляет письмо и фиксирует статус. Ошибка SMTP НЕ откатывает оператора (AC-3)."""
        try:
            send_operator_credentials(operator, temporary_password)
        except Exception as exc:  # SMTP недоступен/ошибка
            logger.error(
                "operator credentials email failed for operator=%s: %s",
                operator.id,
                exc,
            )
            operator.email_status = "error"
            operator.save(update_fields=["email_status"])
            return "error"

        operator.email_status = "sent"
        operator.credentials_sent_at = timezone.now()
        operator.save(update_fields=["email_status", "credentials_sent_at"])
        return "sent"
