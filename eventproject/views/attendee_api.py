"""Story 3.4 — DRF AttendeeViewSet (`/api/v1/attendees/`).

Отдельно от legacy `eventproject/views/attendee.py` (Strangler Fig). Соединяет
RBAC-изоляцию (2.1), residency+ИИН-валидацию (3.1/3.2), конечный автомат (3.3),
пагинацию и RFC7807-ошибки.
"""

import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from eventproject.audit import audit_log
from eventproject.errors import coded_error, conflict_error
from eventproject.models import Attendee
from eventproject.permissions import IsOperator, IsSuperoperator
from eventproject.problem_flags import compute_problem_flags
from eventproject.validators.iin import mask_iin
from eventproject.serializers.attendee import (
    AttendeeListSerializer,
    AttendeeSerializer,
)
from eventproject.serializers.rbac import get_operator_attendee_queryset
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
    # Story 5.3: принимаем multipart (фото/документ) и JSON (поток 5.2 + тесты 3.4).
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    # Story 5.5: поиск по ИМЕНИ (`?search=`). ИИН — EncryptedCharField (Fernet),
    # по нему SQL-поиск невозможен → только ФИО (решение Erda 2026-06-24).
    filter_backends = [SearchFilter]
    search_fields = ["surname", "firstname", "patronymic"]

    def get_serializer_class(self):
        # Story 5.5: список → лёгкий сериализатор с маскированным ИИН; detail/
        # create/update — полный AttendeeSerializer (3.4/5.2/5.3).
        if self.action == "list":
            return AttendeeListSerializer
        return AttendeeSerializer

    def get_queryset(self):
        # RBAC-изоляция (hd-5.3): единый scope-резолвер events ∩ category (404 для
        # чужих). Не дублируем фильтр request__event__in — он внутри резолвера.
        qs = (
            get_operator_attendee_queryset(self.request.user)
            .select_related("request", "category")
            .order_by("-dateAdd")
        )

        # Story 3.4 (AC-5): фильтры списка.
        # BE-10: присутствующий параметр (даже пустой) должен быть валиден — иначе
        # 400. Отсутствующий (None) → фильтр не применяется. Пустая строка `?x=`
        # больше не игнорируется молча (консистентно с невалидным значением).
        category_id = self.request.query_params.get("category_id")
        if category_id is not None:
            try:
                category_id = int(category_id)
            except (TypeError, ValueError):
                raise coded_error("param_not_int", field="category_id")
            qs = qs.filter(category_id=category_id)

        status_param = self.request.query_params.get("status")
        if status_param is not None:
            if status_param not in ATTENDEE_STATUSES:
                raise coded_error("status_invalid", field="status")
            qs = qs.filter(status=status_param)

        return qs

    def perform_create(self, serializer):
        # RBAC-проверка владения мероприятием выполняется в
        # AttendeeSerializer.validate() (единый источник для create и update).
        # status по умолчанию draft; dateAdd ставит сервер.
        #
        # Story 5.3 — two-phase upload (AC-5): валидация (Pillow size/ratio/resolution
        # + PDF→JPEG) уже выполнена сериализатором ДО записи (orphaned record не
        # возникает — невалидный файл не доходит до save). Запись + аудит атомарны;
        # если аудит упадёт — удаляем только что записанные медиафайлы, чтобы не
        # осталось orphaned files (файл без записи). Удаление записи (любой статус)
        # чистит файлы через post_delete Signal (eventproject/signals.py).
        with transaction.atomic():
            attendee = serializer.save(dateAdd=timezone.now())
            try:
                audit_log(
                    user=self.request.user,
                    action="attendee.create",
                    obj_type="Attendee",
                    obj_id=str(attendee.id),
                    ip=self.request.META.get("REMOTE_ADDR", ""),
                )
            except Exception:
                for field in ("photo", "docScan"):
                    file = getattr(attendee, field, None)
                    if file:
                        file.delete(save=False)
                raise

    # ── Edit-lock после ready/exported (FR22) ────────────────────────────
    def _ensure_editable(self):
        instance = self.get_object()
        if instance.status in _EDIT_LOCKED_STATUSES:
            raise PermissionDenied(_EDIT_LOCKED_MESSAGE)
        return instance

    def _audit_write(self, request, action, obj_id):
        # Аудит мутаций/удаления PII (Story 3.4 review): audit.py документирует
        # attendee.update / attendee.delete как ожидаемые экшены.
        audit_log(
            user=request.user,
            action=action,
            obj_type="Attendee",
            obj_id=str(obj_id),
            ip=request.META.get("REMOTE_ADDR", ""),
        )

    def _audit_iin_discard(self, request, old_iin, instance):
        # P1-10: при РК→не-РК ранее сохранённый ИИН отбрасывается (resolve_residency
        # → iin=None). Фиксируем это в аудите (МАСКИРОВАННЫЙ ИИН), иначе PII исчезает
        # без следа при редактировании резидентства.
        if old_iin and not instance.iin:
            audit_log(
                user=request.user,
                action="attendee.iin_discarded",
                obj_type="Attendee",
                obj_id=str(instance.pk),
                ip=request.META.get("REMOTE_ADDR", ""),
                extra={"iin": mask_iin(old_iin)},
            )

    # P1-5: save/delete + аудит атомарны (паритет с perform_create). Сбой аудита
    # откатывает мутацию → нет «правки/удаления без аудит-строки». Откат безопасен:
    # post_delete/pre_save чистят файлы через transaction.on_commit (signals.py),
    # который при откате НЕ срабатывает — старый файл сохраняется.
    #
    # ВАЖНО: НЕ переопределяем partial_update — DRF-дефолт делегирует в self.update()
    # (см. UpdateModelMixin.partial_update → self.update(partial=True)). Отдельный
    # override плодил бы двойной аудит (PATCH логировался дважды). PATCH идёт через
    # этот update().
    def update(self, request, *args, **kwargs):
        instance = self._ensure_editable()
        old_iin = instance.iin
        with transaction.atomic():
            response = super().update(request, *args, **kwargs)
            instance.refresh_from_db()
            self._audit_iin_discard(request, old_iin, instance)
            self._audit_write(request, "attendee.update", instance.pk)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self._ensure_editable()
        obj_id = instance.pk
        with transaction.atomic():
            response = super().destroy(request, *args, **kwargs)
            self._audit_write(request, "attendee.delete", obj_id)
        return response

    # ── Переход draft → submitted (операторский submit, AC-6) ────────────
    @action(detail=True, methods=["post"], permission_classes=[IsOperator])
    def submit(self, request, pk=None):
        attendee = self.get_object()

        # Все обязательные поля + валидный ИИН (для резидента РК).
        result = resolve_residency(
            attendee.countryId, attendee.iin, attendee.birthDate
        )
        if result.error:
            # fe-1.1: машинный код (iin_checksum/iin_dob_mismatch/…) + params, не generic.
            raise coded_error(result.code or "unknown", field="iin", **(result.params or {}))

        try:
            assert_transition(attendee.status, AttendeeStatus.SUBMITTED)
        except InvalidStatusTransition as exc:
            raise coded_error("status_transition_invalid", field="status")

        old_status = attendee.status
        attendee.status = AttendeeStatus.SUBMITTED
        # Story fe-3.1: фиксируем проблемные флаги при submit → DTO очереди читает
        # хранимое поле, ?problem=-фильтр работает с серверной пагинацией.
        attendee.problem_flags = compute_problem_flags(attendee)
        attendee.save(update_fields=["status", "problem_flags"])
        audit_log(
            user=request.user,
            action="attendee.status_change",
            obj_type="Attendee",
            obj_id=str(attendee.id),
            ip=request.META.get("REMOTE_ADDR", ""),
            extra={"from": old_status, "to": AttendeeStatus.SUBMITTED},
        )
        return Response(AttendeeSerializer(attendee).data)

    # ── Anti-churn audit-хелпер решений проверяющего (fe-3.4 реш.#3) ──────
    def _record_decision(self, attendee, action, actor, *, from_status=None,
                         to_status=None, reason=None):
        """Единая точка записи решения проверяющего (approve/return) в аудит.

        fe-3.4 (approve) и fe-3.5 (return) идут через ЭТОТ хелпер, чтобы fe-3.6
        (durable AuditLog + concurrency-guard) менял ТОЛЬКО его внутренности, не трогая
        call-sites. Sink сейчас = текущий `audit_log()` (durable DB-`AuditLog` с hd-4.1 +
        stdout-зеркало; PII-скраб внутри). `from_status`/`to_status` → extra ({from,to});
        `reason` (fe-3.5 возврат) — тоже в extra, если задан.
        """
        extra = {}
        if from_status is not None or to_status is not None:
            extra["from"] = from_status
            extra["to"] = to_status
        if reason is not None:
            extra["reason"] = reason
        audit_log(
            user=actor,
            action=action,
            obj_type="Attendee",
            obj_id=str(attendee.id),
            ip=self.request.META.get("REMOTE_ADDR", ""),
            extra=extra or None,
        )

    # ── Переход in_review → ready (решение «Одобрить», fe-3.4) ────────────
    @action(detail=True, methods=["post"], permission_classes=[IsSuperoperator])
    def approve(self, request, pk=None):
        """fe-3.4: одобрение заявки админом-проверяющим (in_review → ready).

        Mirror submit-экшена, но: (1) FSM-цель READY (вперёд, к экспорту — НЕ submitted,
        это возврат fe-3.5); (2) guard не-in_review → 409 Conflict (`conflict_error`, НЕ
        400 — нельзя двойной/нелегальный переход); (3) audit через anti-churn
        `_record_decision` (fe-3.6 меняет ТОЛЬКО внутрь); (4) ответ masked-safe `{id, status}`
        — НЕ `AttendeeSerializer` (он отдаёт сырой ИИН на admin-поверхность, реш.#6).
        scope/RBAC/404 наследуются (IsSuperoperator + get_operator_attendee_queryset).
        """
        attendee = self.get_object()
        with transaction.atomic():
            try:
                assert_transition(attendee.status, AttendeeStatus.READY)
            except InvalidStatusTransition:
                raise conflict_error("status_transition_invalid", field="status")
            old_status = attendee.status
            attendee.status = AttendeeStatus.READY
            attendee.save(update_fields=["status"])
            self._record_decision(
                attendee,
                "attendee.approved",
                request.user,
                from_status=old_status,
                to_status=AttendeeStatus.READY,
            )
        return Response({"id": attendee.id, "status": attendee.status})

    # ── Переход in_review → submitted (решение «Вернуть с причиной», fe-3.5) ──
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsSuperoperator],
        url_path="return",
    )
    def return_to_operator(self, request, pk=None):
        """fe-3.5: возврат заявки оператору админом-проверяющим (in_review → submitted).

        Mirror approve, но: (1) FSM-цель SUBMITTED (назад к оператору — НЕ новый статус
        «Возвращена»: это submitted+return_count>0; FSM не имеет RETURNED, state_machine.py);
        (2) `reason` ОБЯЗАТЕЛЕН → 400 при пустом (отдельно от 409-guard); (3) пишем хранимые
        last_return_reason + return_count (continuity 3.3/3.7); (4) audit action="attendee.returned"
        с reason через `_record_decision`; (5) ответ masked-safe {id, status} (реш.#6).
        ⚠ метод НЕ `def return` — Python keyword → url_path="return".
        """
        attendee = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            # reason обязателен (AC, UX-DR9). Это 400 (валидация ввода), НЕ 409 (статус-guard).
            raise coded_error("required", field="reason")
        with transaction.atomic():
            # ⚠ Guard = ИМЕННО in_review, НЕ assert_transition(status, SUBMITTED): FSM
            # разрешает и draft→submitted (это submit ОПЕРАТОРА, не возврат проверяющего),
            # поэтому одной проверки перехода мало. Возврат легален только из «На проверке».
            if attendee.status != AttendeeStatus.IN_REVIEW:
                raise conflict_error("status_transition_invalid", field="status")
            old_status = attendee.status
            attendee.status = AttendeeStatus.SUBMITTED
            attendee.last_return_reason = reason
            attendee.return_count = (attendee.return_count or 0) + 1
            attendee.save(
                update_fields=["status", "last_return_reason", "return_count"]
            )
            self._record_decision(
                attendee,
                "attendee.returned",
                request.user,
                from_status=old_status,
                to_status=AttendeeStatus.SUBMITTED,
                reason=reason,
            )
        return Response({"id": attendee.id, "status": attendee.status})
