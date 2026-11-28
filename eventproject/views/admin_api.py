"""Страницы администратора (суперпользователя) для Next.js: `/api/v1/admin/…`.

Повторяют HTML-вьюхи старой АЦ — те же правила, тексты сообщений и аудит:

* главная `/avmac/` (`views.index`) → `GET admin/home/`;
* `create_event` → `POST admin/events/`;
* `show_event` → `GET admin/events/<id>/`;
* `delete_event` (вместе с папкой файлов) → `DELETE admin/events/<id>/`;
* `bind_operators`, `add_operator_to_event` → `POST admin/events/<id>/operators/`;
* `unbind_event` → `DELETE admin/events/<id>/operators/<operator_id>/`;
* `add_operator` (+ письмо со ссылкой) → `POST admin/operators/`;
* `show_operator` → `GET admin/operators/<id>/`;
* `new_password` → `POST admin/operators/<id>/new-password/`;
* `delete_operator` → `DELETE admin/operators/<id>/`.

Выгрузки (JSON-сверки, ZIP фото) остаются прежними адресами Django
(`/download_*`), интерфейс вызывает их напрямую.
"""

import logging
import os
import shutil
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from directories.models import City
from eventproject.audit import audit_log
from eventproject.models import Event, Operator, Request
from eventproject.operator_activation import send_operator_link
from eventproject.permissions import IsSuperuser
from eventproject.serializers.event import event_brief

logger = logging.getLogger("eventproject")

# Главная администратора и карточка оператора показывают мероприятия на 900 дней вперёд.
ADMIN_DAYS = 900


def _ip(request):
    return request.META.get("REMOTE_ADDR", "")


def _fail(message, http_status=status.HTTP_400_BAD_REQUEST, code="admin_error"):
    """Ошибка с текстом старой страницы (админка старой АЦ — только по-русски)."""
    return Response({"type": code, "field": None, "params": {}, "detail": message}, status=http_status)


def _cities():
    return [{"code": c.city_code, "name_rus": c.name_rus, "name_kaz": c.name_kaz, "name_eng": c.name_eng} for c in City.objects.all()]


def _operator_row(op):
    user = op.user
    return {
        "id": op.id,
        "username": user.username,
        "last_name": user.last_name,
        "first_name": user.first_name,
        "patronymic": op.patronymic or "",
        "email": user.email,
        "phone_number": op.phone_number or "",
        "workplace": op.workplace or "",
        "role": op.role,
        "is_active": user.is_active,
        "email_status": op.email_status,
    }


def _request_row(req):
    creator = req.created_by.user
    return {
        "id": req.id,
        "name": req.name,
        "status": req.status,
        "date_created": req.date_created,
        "registration_time": req.registration_time,
        "event_id": req.event_id,
        "created_by": f"{creator.first_name} {creator.last_name}".strip() or creator.username,
    }


def _upcoming(queryset):
    start = date.today()
    return queryset.filter(date_end__range=[start, start + timedelta(days=ADMIN_DAYS)])


@api_view(["GET"])
@permission_classes([IsSuperuser])
def admin_home(request):
    """Главная `/avmac/`: мероприятия на 900 дней вперёд, все операторы, города."""
    operators = Operator.objects.select_related("user").prefetch_related("events").order_by(
        "user__last_name", "user__first_name"
    )
    return Response(
        {
            "events": [event_brief(e) for e in _upcoming(Event.objects.all()).order_by("date_start")],
            "operators": [dict(_operator_row(o), event_ids=[e.id for e in o.events.all()]) for o in operators],
            "cities": _cities(),
        }
    )


@api_view(["POST"])
@permission_classes([IsSuperuser])
def admin_create_event(request):
    """`create_event`: те же проверки и те же сообщения."""
    data = request.data
    name_rus = str(data.get("name_rus", "") or "")
    name_kaz = str(data.get("name_kaz", "") or "")
    name_eng = str(data.get("name_eng", "") or "")
    event_code = str(data.get("event_code", "") or "")
    city = str(data.get("city", "") or "")
    try:
        sd = datetime.strptime(str(data.get("date_start", "")), "%Y-%m-%d").date()
        ed = datetime.strptime(str(data.get("date_end", "")), "%Y-%m-%d").date()
    except ValueError:
        return _fail("Не удалось создать мероприятие. Укажите даты начала и окончания.")
    if name_rus == "":
        return _fail("Не удалось создать мероприятие. Название мероприятия отсутствует")
    if ed < sd:
        return _fail("Не удалось создать мероприятие. Дата окончания не может быть раньше даты создания")
    if ed < date.today():
        return _fail("Не удалось создать мероприятие. Истек дата окончания")
    event = Event.objects.create(
        name_kaz=name_kaz, name_rus=name_rus, name_eng=name_eng, event_code=event_code,
        date_start=sd, date_end=ed, title=name_rus, start_date=sd, end_date=ed, city_code=city,
        created_by=request.user,
    )
    audit_log(user=request.user, action="event.create", obj_type="Event", obj_id=str(event.pk), ip=_ip(request))
    return Response(
        {"event": event_brief(event), "message": "Мероприятие " + name_rus + " успешно создано"},
        status=status.HTTP_201_CREATED,
    )


def _archive_info(event_id):
    """Заранее собранный `event_<id>.zip` в рабочем каталоге (как `show_event`)."""
    zip_name = f"event_{event_id}.zip"
    if not os.path.isfile(zip_name):
        return None
    return {
        "name": zip_name,
        "size_mb": round(os.path.getsize(zip_name) / 1000000, 2),
        "modified": datetime.fromtimestamp(os.path.getmtime(zip_name)),
    }


@api_view(["GET", "DELETE"])
@permission_classes([IsSuperuser])
def admin_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if request.method == "DELETE":
        return _delete_event(request, event)

    operators = list(Operator.objects.filter(events=event).select_related("user"))
    assigned = {o.pk for o in operators}
    others = Operator.objects.exclude(pk__in=assigned).select_related("user").order_by("user__last_name")
    sent = Request.objects.filter(event=event, status__in=["Sent", "Exported"]).select_related("created_by__user")
    active = Request.objects.filter(event=event, status__in=["Active", "Checking"]).select_related("created_by__user")
    return Response(
        {
            "event": event_brief(event),
            "city_name": next((c.name_rus for c in City.objects.filter(city_code=event.city_code)), ""),
            "operators": [_operator_row(o) for o in operators],
            "other_operators": [_operator_row(o) for o in others],
            "requests": [_request_row(r) for r in sent],
            "active_requests": [_request_row(r) for r in active],
            "unexported": sent.exclude(status="Exported").count(),
            "archive": _archive_info(event.id),
            # Для формы «Добавить оператора» на карточке — тот же список, что на главной.
            "events": [event_brief(e) for e in _upcoming(Event.objects.all()).order_by("date_start")],
        }
    )


def _delete_event(request, event):
    """`delete_event`: сначала папка файлов мероприятия, затем записи."""
    mydir = os.path.join(settings.MEDIA_ROOT, f"event_{event.id}")
    try:
        shutil.rmtree(mydir)
    except FileNotFoundError:
        pass
    except OSError:
        logger.error("Event media cleanup failed")
        return _fail("Не удалось удалить файлы мероприятия.", status.HTTP_503_SERVICE_UNAVAILABLE)
    message = "Мероприятие: " + (event.name_rus or "") + " успешно удалено"
    event_pk = str(event.id)
    event.delete()
    audit_log(user=request.user, action="event.delete", obj_type="Event", obj_id=event_pk, ip=_ip(request))
    return Response({"message": message})


@api_view(["POST"])
@permission_classes([IsSuperuser])
def admin_bind_operators(request, event_id):
    """`bind_operators` / `add_operator_to_event`: выдать операторам доступ к мероприятию."""
    event = get_object_or_404(Event, pk=event_id)
    ids = request.data.get("operator_ids")
    if not isinstance(ids, list) or not ids:
        return _fail("Не удалось привязать операторов. Проверьте мероприятие и выбранных операторов.")
    try:
        selected = [Operator.objects.select_related("user").get(id=int(o)) for o in ids]
    except (TypeError, ValueError, Operator.DoesNotExist):
        return _fail("Не удалось привязать операторов. Проверьте мероприятие и выбранных операторов.")
    for operator in selected:
        operator.events.add(event)
    audit_log(
        user=request.user, action="event.operators_bound", obj_type="Event", obj_id=str(event.pk), ip=_ip(request),
        extra={"operators": [o.pk for o in selected]},
    )
    if len(selected) == 1:
        u = selected[0].user
        message = f"Пользователью {u.last_name} {u.first_name} успешно предоставлен доступ на мероприятие {event.name_rus}"
    else:
        message = "Операторы успешно добавлены"
    return Response({"message": message})


@api_view(["DELETE"])
@permission_classes([IsSuperuser])
def admin_unbind_operator(request, event_id, operator_id):
    """`unbind_event`: снять доступ оператора к мероприятию."""
    event = get_object_or_404(Event, pk=event_id)
    operator = get_object_or_404(Operator.objects.select_related("user"), pk=operator_id)
    operator.events.remove(event)
    audit_log(
        user=request.user, action="event.operator_unbound", obj_type="Event", obj_id=str(event.pk), ip=_ip(request),
        extra={"operator": operator.pk},
    )
    u = operator.user
    return Response({"message": f"{event.name_rus} успешно откреплен от пользователя {u.last_name} {u.first_name}"})


@api_view(["POST"])
@permission_classes([IsSuperuser])
def admin_create_operator(request):
    """`add_operator`: учётка без пароля + доступ к мероприятию + письмо со ссылкой."""
    data = request.data
    try:
        email = str(data.get("email", "")).strip()
        validate_email(email)
        with transaction.atomic():
            event = Event.objects.get(pk=data["event"])
            user = User.objects.create_user(
                username=data["login"], email=email, password=None,
                first_name=data["first_name"], last_name=data["last_name"],
            )
            operator = Operator.objects.create(
                user=user, phone_number=data["phone_number"], patronymic=data["patronymic"], workplace=data["workplace"],
            )
            operator.events.add(event)
    except (KeyError, ValueError, TypeError, ValidationError, IntegrityError, Event.DoesNotExist):
        return _fail("Проверьте данные оператора, email и уникальность логина.")
    audit_log(user=request.user, action="operator.create", obj_type="Operator", obj_id=str(operator.pk), ip=_ip(request))
    sent = send_operator_link(operator)
    return Response(
        {
            "operator": _operator_row(operator),
            "email_sent": sent,
            "message": (
                "Оператор создан. Ссылка для установки пароля отправлена на его email."
                if sent
                else "Оператор создан. Письмо не отправлено. Проверьте настройки почты и повторите отправку из карточки оператора."
            ),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "DELETE"])
@permission_classes([IsSuperuser])
def admin_operator(request, operator_id):
    operator = get_object_or_404(Operator.objects.select_related("user"), pk=operator_id)
    if request.method == "DELETE":
        u = operator.user
        message = f"{u.first_name} {u.last_name} успешно удален"
        op_pk = str(operator.pk)
        operator.delete()
        u.delete()
        audit_log(user=request.user, action="operator.delete", obj_type="Operator", obj_id=op_pk, ip=_ip(request))
        return Response({"message": message})
    events = _upcoming(operator.events.all()).order_by("-date_start")
    reqs = Request.objects.filter(created_by=operator).select_related("created_by__user").order_by("-date_created")
    return Response(
        {
            "operator": _operator_row(operator),
            "events": [event_brief(e) for e in events],
            "requests": [_request_row(r) for r in reqs],
        }
    )


@api_view(["POST"])
@permission_classes([IsSuperuser])
def admin_operator_new_password(request, operator_id):
    """`new_password`: повторно отправить ссылку для установки пароля."""
    operator = get_object_or_404(Operator.objects.select_related("user"), pk=operator_id)
    if send_operator_link(operator):
        return Response({"email_sent": True, "message": "Ссылка для установки пароля отправлена оператору."})
    return Response(
        {
            "email_sent": False,
            "message": "Письмо не отправлено. Проверьте активность учётной записи, email оператора и настройки почты.",
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
