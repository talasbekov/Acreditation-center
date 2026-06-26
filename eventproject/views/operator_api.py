"""Story 2.3 — DRF API онбординга операторов (`/api/v1/operators/`).

Отдельный модуль от legacy `eventproject/views/operator.py` (function-based
`add_operator`), чтобы не ломать существующий Django-UI (Strangler Fig).
"""

import logging

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from eventproject.audit import audit_log
from eventproject.errors import coded_error
from eventproject.models import Operator
from eventproject.permissions import IsSuperoperator
from eventproject.serializers import (
    OperatorCreateSerializer,
    OperatorReadSerializer,
    OperatorRegistryDetailSerializer,
    OperatorRegistryListSerializer,
)
from eventproject.services.access_events import record_access_event
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
    # Story 2.4 (AC-2): поиск по ФИО/username/email через встроенный DRF SearchFilter
    # (django-filter не установлен — новую зависимость не вводим). `?search=...`.
    filter_backends = [SearchFilter]
    search_fields = [
        "user__last_name",
        "user__first_name",
        "patronymic",
        "user__username",
        "user__email",
    ]

    def get_queryset(self):
        qs = (
            Operator.objects.select_related("user", "category")
            .prefetch_related("events")
            .order_by("user__last_name", "user__first_name", "id")
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related("access_events__actor")

        # Story 2.4 (AC-2): точечные фильтры реестра.
        event_id = self.request.query_params.get("event_id")
        if event_id:
            # Невалидный event_id → 400, а не 500 (ValueError в events__id=).
            try:
                event_id = int(event_id)
            except (TypeError, ValueError):
                raise coded_error("param_not_int", field="event_id")
            # M2M-фильтр может дублировать строки → distinct().
            qs = qs.filter(events__id=event_id).distinct()
        email_status = self.request.query_params.get("email_status")
        if email_status:
            # Невалидный статус → 400, иначе пустой результат неотличим от «нет совпадений».
            valid_statuses = {c[0] for c in Operator.EMAIL_STATUS_CHOICES}
            if email_status not in valid_statuses:
                raise coded_error("email_status_invalid", field="email_status")
            qs = qs.filter(email_status=email_status)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return OperatorCreateSerializer
        if self.action == "list":
            return OperatorRegistryListSerializer
        if self.action == "retrieve":
            return OperatorRegistryDetailSerializer
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
        # Story 2.4: фиксируем событие в истории доступа (queryable).
        # Best-effort: оператор уже создан — сбой записи истории не должен ломать 201.
        try:
            record_access_event(
                operator,
                "created",
                actor=request.user,
                ip=request.META.get("REMOTE_ADDR", ""),
            )
        except Exception:
            logger.exception(
                "failed to record created access event for operator=%s", operator.id
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

    @action(detail=True, methods=["post"], permission_classes=[IsSuperoperator])
    def deactivate(self, request, pk=None):
        """Story 2.4 (AC-4): soft-деактивация оператора (is_active=False)."""
        operator = self.get_object()
        user = operator.user

        if user == request.user:
            return Response(
                {"detail": "Нельзя деактивировать собственный аккаунт."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.is_superuser:
            return Response(
                {"detail": "Нельзя деактивировать суперпользователя."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # P2-1: супероператор не может деактивировать другого супероператора (взаимная
        # блокировка). Только суперпользователь (админ) вправе деактивировать супероператора.
        if getattr(operator, "role", None) == "superoperator" and not request.user.is_superuser:
            return Response(
                {"detail": "Супероператор не может деактивировать другого супероператора."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
            record_access_event(
                operator,
                "deactivated",
                actor=request.user,
                ip=request.META.get("REMOTE_ADDR", ""),
            )
            audit_log(
                user=request.user,
                action="operator.deactivate",
                obj_type="User",
                obj_id=user.id,
                ip=request.META.get("REMOTE_ADDR", ""),
            )

        return Response(
            OperatorRegistryDetailSerializer(operator).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsSuperoperator])
    def reactivate(self, request, pk=None):
        """Story 2.4 (AC-4): обратная операция — возврат доступа."""
        operator = self.get_object()
        user = operator.user

        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
            record_access_event(
                operator,
                "reactivated",
                actor=request.user,
                ip=request.META.get("REMOTE_ADDR", ""),
            )
            audit_log(
                user=request.user,
                action="operator.reactivate",
                obj_type="User",
                obj_id=user.id,
                ip=request.META.get("REMOTE_ADDR", ""),
            )

        return Response(
            OperatorRegistryDetailSerializer(operator).data,
            status=status.HTTP_200_OK,
        )

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
