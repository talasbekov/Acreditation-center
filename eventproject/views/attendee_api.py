"""Story 3.4 — DRF AttendeeViewSet (`/api/v1/attendees/`).

Отдельно от legacy `eventproject/views/attendee.py` (Strangler Fig). Соединяет
RBAC-изоляцию (2.1), residency+ИИН-валидацию (3.1/3.2), конечный автомат (3.3),
пагинацию и RFC7807-ошибки.
"""

import logging

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from eventproject.audit import audit_log
from eventproject.models import Attendee
from eventproject.permissions import IsOperator
from eventproject.serializers.attendee import AttendeeSerializer
from eventproject.serializers.rbac import get_operator_events
from eventproject.state_machine import (
    ATTENDEE_STATUSES,
    AttendeeStatus,
    InvalidStatusTransition,
    assert_transition,
)
from eventproject.validators.residency import resolve_residency

logger = logging.getLogger("eventproject")

# Статусы, после которых редактирование заблокировано (FR22).
_EDIT_LOCKED_STATUSES = {AttendeeStatus.READY, AttendeeStatus.EXPORTED}

_EDIT_LOCKED_MESSAGE = "Редактирование заблокировано после одобрения"


class AttendeeViewSet(viewsets.ModelViewSet):
    """CRUD участников для Оператора (с RBAC-изоляцией по мероприятиям)."""

    permission_classes = [IsOperator]
    serializer_class = AttendeeSerializer

    def get_queryset(self):
        # RBAC-изоляция: только участники мероприятий оператора (404 для чужих).
        events = get_operator_events(self.request.user)
        qs = (
            Attendee.objects.filter(request__event__in=events)
            .select_related("request", "category")
            .order_by("-dateAdd")
        )

        # Story 3.4 (AC-5): фильтры списка.
        category_id = self.request.query_params.get("category_id")
        if category_id:
            try:
                category_id = int(category_id)
            except (TypeError, ValueError):
                raise ValidationError({"category_id": "Должно быть целым числом."})
            qs = qs.filter(category_id=category_id)

        status_param = self.request.query_params.get("status")
        if status_param:
            if status_param not in ATTENDEE_STATUSES:
                raise ValidationError(
                    {"status": f"Допустимые значения: {sorted(ATTENDEE_STATUSES)}"}
                )
            qs = qs.filter(status=status_param)

        return qs

    def perform_create(self, serializer):
        req = serializer.validated_data.get("request")
        # Нельзя создать участника в чужом мероприятии (RBAC).
        if req is None or not get_operator_events(self.request.user).filter(
            id=req.event_id
        ).exists():
            raise PermissionDenied("Нет доступа к этому мероприятию.")
        # status по умолчанию draft; dateAdd ставит сервер.
        attendee = serializer.save(dateAdd=timezone.now())
        audit_log(
            user=self.request.user,
            action="attendee.create",
            obj_type="Attendee",
            obj_id=str(attendee.id),
            ip=self.request.META.get("REMOTE_ADDR", ""),
        )

    # ── Edit-lock после ready/exported (FR22) ────────────────────────────
    def _ensure_editable(self):
        instance = self.get_object()
        if instance.status in _EDIT_LOCKED_STATUSES:
            raise PermissionDenied(_EDIT_LOCKED_MESSAGE)
        return instance

    def update(self, request, *args, **kwargs):
        self._ensure_editable()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._ensure_editable()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._ensure_editable()
        return super().destroy(request, *args, **kwargs)

    # ── Переход draft → submitted (операторский submit, AC-6) ────────────
    @action(detail=True, methods=["post"], permission_classes=[IsOperator])
    def submit(self, request, pk=None):
        attendee = self.get_object()

        # Все обязательные поля + валидный ИИН (для резидента РК).
        result = resolve_residency(
            attendee.countryId, attendee.iin, attendee.birthDate
        )
        if result.error:
            raise ValidationError({"iin": result.error})

        try:
            assert_transition(attendee.status, AttendeeStatus.SUBMITTED)
        except InvalidStatusTransition as exc:
            raise ValidationError({"status": str(exc)})

        old_status = attendee.status
        attendee.status = AttendeeStatus.SUBMITTED
        attendee.save(update_fields=["status"])
        audit_log(
            user=request.user,
            action="attendee.status_change",
            obj_type="Attendee",
            obj_id=str(attendee.id),
            ip=request.META.get("REMOTE_ADDR", ""),
            extra={"from": old_status, "to": AttendeeStatus.SUBMITTED},
        )
        return Response(AttendeeSerializer(attendee).data)
