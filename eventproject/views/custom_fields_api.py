"""Дополнительные поля мероприятия (второй этап).

GET/POST `events/<id>/custom-fields/`, PUT/DELETE `custom-fields/<id>/`.
Видят и меняют поля те, кому доступно мероприятие: оператор, привязанный к нему,
супероператор и администратор (`get_operator_events`). Не больше 20 полей.
"""

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from eventproject.audit import audit_log
from eventproject.errors import coded_error
from eventproject.models import CustomField
from eventproject.permissions import IsOperator
from eventproject.serializers.rbac import get_operator_events
from eventproject.services.custom_fields import field_payload


def _ip(request):
    return request.META.get("REMOTE_ADDR", "")


def _read(data, instance=None):
    """Проверить ввод поля; вернуть dict атрибутов модели."""
    name = str(data.get("field_name", getattr(instance, "field_name", "")) or "").strip()
    if not name:
        raise coded_error("required", field="field_name")
    if len(name) > 255:
        raise coded_error("max_length", field="field_name")
    field_type = data.get("field_type", getattr(instance, "field_type", "text"))
    if field_type not in dict(CustomField.TYPE_CHOICES):
        raise coded_error("invalid_choice", field="field_type")
    options = data.get("options", getattr(instance, "options", []))
    if isinstance(options, str):
        options = [o.strip() for o in options.split("\n")]
    if not isinstance(options, list):
        raise coded_error("invalid", field="options")
    options = [str(o).strip() for o in options if str(o).strip()]
    if field_type == "select" and not options:
        raise coded_error("custom_field_options_required", field="options")
    if field_type != "select":
        options = []
    try:
        sort_order = int(data.get("sort_order", getattr(instance, "sort_order", 0)) or 0)
    except (TypeError, ValueError):
        raise coded_error("param_not_int", field="sort_order")
    return {
        "field_name": name,
        "field_type": field_type,
        "is_required": bool(data.get("is_required", getattr(instance, "is_required", False))),
        "options": options,
        "sort_order": sort_order,
    }


@api_view(["GET", "POST"])
@permission_classes([IsOperator])
def event_custom_fields(request, event_id):
    event = get_object_or_404(get_operator_events(request.user), pk=event_id)
    if request.method == "GET":
        return Response({"results": [field_payload(f) for f in CustomField.objects.filter(event=event)]})

    attrs = _read(request.data)
    with transaction.atomic():
        if CustomField.objects.select_for_update().filter(event=event).count() >= CustomField.MAX_PER_EVENT:
            raise coded_error("custom_field_limit", field="field_name")
        if "sort_order" not in request.data:
            attrs["sort_order"] = CustomField.objects.filter(event=event).count()
        try:
            field = CustomField.objects.create(event=event, created_by=request.user, **attrs)
        except IntegrityError:
            raise coded_error("custom_field_name_taken", field="field_name")
    audit_log(user=request.user, action="custom_field.create", obj_type="CustomField", obj_id=str(field.pk), ip=_ip(request))
    return Response(field_payload(field), status=status.HTTP_201_CREATED)


@api_view(["PUT", "PATCH", "DELETE"])
@permission_classes([IsOperator])
def custom_field_detail(request, field_id):
    field = get_object_or_404(CustomField.objects.filter(event__in=get_operator_events(request.user)), pk=field_id)
    if request.method == "DELETE":
        pk = str(field.pk)
        field.delete()
        audit_log(user=request.user, action="custom_field.delete", obj_type="CustomField", obj_id=pk, ip=_ip(request))
        return Response(status=status.HTTP_204_NO_CONTENT)
    attrs = _read(request.data, field)
    for key, value in attrs.items():
        setattr(field, key, value)
    try:
        field.save()
    except IntegrityError:
        raise coded_error("custom_field_name_taken", field="field_name")
    audit_log(user=request.user, action="custom_field.update", obj_type="CustomField", obj_id=str(field.pk), ip=_ip(request))
    return Response(field_payload(field))
