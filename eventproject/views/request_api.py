"""Заявки (`/api/v1/requests/`) и кабинет оператора (`/api/v1/cabinet/`).

Повторяет HTML-страницы оператора (views/views.py `application`, `preview`,
`back_to_change`, `send`; views/request.py `create_request`, `show_request`,
`delete_request`) — те же права, статусы и аудит, через те же сервисы.

* Список без параметров — все заявки мероприятий пользователя (селектор формы
  участника в React-SPA, как раньше). `?mine=1` — только свои заявки, как в кабинете.
* Карточка, отправка и возврат к редактированию — только своя заявка
  (`owned_request`), суперпользователь видит любую (как `show_request_to_admin`).
"""

from datetime import date, timedelta

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response

from directories.models import City
from eventproject.audit import audit_log
from eventproject.models import Attendee, Event, Operator, Request
from eventproject.permissions import IsOperator
from eventproject.serializers.attendee import AttendeeSerializer
from eventproject.serializers.event import event_brief
from eventproject.serializers.rbac import get_operator_events
from eventproject.serializers.request import RequestSerializer, request_payload
from eventproject.services import lifecycle
from eventproject.view_helpers import owned_requests

# Кабинет показывает мероприятия, которые закончатся в ближайшие 600 дней (как `application`).
CABINET_DAYS = 600


class RequestConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "request_closed"
    default_detail = "Заявка отправлена — добавить участника нельзя."


def _ip(request):
    return request.META.get("REMOTE_ADDR", "")


def _operator_or_403(user):
    try:
        return user.operator
    except Operator.DoesNotExist as exc:
        raise PermissionDenied("Требуется профиль оператора") from exc


class RequestViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOperator]
    serializer_class = RequestSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if self.action == "list":
            if self.request.query_params.get("mine") in ("1", "true", "yes"):
                return owned_requests(user).select_related("event").order_by("-date_created")
            events = get_operator_events(user)
            qs = Request.objects.filter(event__in=events).select_related("event").order_by("event_id", "id")
            event_id = self.request.query_params.get("event")
            if event_id and event_id.isdigit():
                qs = qs.filter(event_id=int(event_id))
            return qs
        if user.is_superuser:
            return Request.objects.select_related("event", "created_by__user")
        return owned_requests(user).select_related("event", "created_by__user")

    def create(self, request, *args, **kwargs):
        """«+ Создать новый список участников (заявку)» — `create_request`."""
        event_id = request.data.get("event")
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            from eventproject.errors import coded_error

            raise coded_error("required", field="event")
        event = get_object_or_404(get_operator_events(request.user), pk=event_id)
        operator = _operator_or_403(request.user)
        now = timezone.now()
        req = Request.objects.create(
            name=now.strftime("%d%m%Y%H%M%S"),
            event=event,
            status=lifecycle.REQUEST_ACTIVE,
            date_created=now,
            created_by=operator,
            registration_time=now,
        )
        audit_log(user=request.user, action="request.create", obj_type="Request", obj_id=str(req.pk), ip=_ip(request))
        return Response(request_payload(req, request), status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        req = self.get_object()
        return Response(request_payload(req, request, with_attendees=True))

    def destroy(self, request, *args, **kwargs):
        """«удалить список» — `delete_request` (вместе с участниками)."""
        req = self.get_object()
        req_pk = str(req.pk)
        req.delete()
        audit_log(user=request.user, action="request.delete", obj_type="Request", obj_id=req_pk, ip=_ip(request))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        """«Отправить» — все черновики заявки уходят на проверку, всё или ничего."""
        req = self.get_object()
        try:
            result = lifecycle.submit_request(req.pk, request.user, _ip(request))
        except lifecycle.LifecycleError as exc:
            names = {
                a.pk: " ".join(p for p in (a.surname, a.firstname) if p) or f"#{a.pk}"
                for a in Attendee.objects.filter(pk__in=exc.problems or {})
            }
            body = {
                "type": "request_not_ready" if exc.problems else f"request_{exc.code or 'not_ready'}",
                "field": None,
                "params": {},
                "detail": lifecycle.lifecycle_message(exc, "ru"),
                "problems": [
                    {"attendee_id": pk, "name": names.get(pk, f"#{pk}"), "codes": codes}
                    for pk, codes in sorted((exc.problems or {}).items())
                ],
            }
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        req.refresh_from_db()
        payload = request_payload(req, request, with_attendees=True)
        payload["already_sent"] = bool(getattr(result, "already_sent", False))
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="back-to-change")
    def back_to_change(self, request, pk=None):
        """«Вернуться к редактированию» — снимает только прежний статус Checking."""
        req = lifecycle.leave_legacy_preview(self.get_object())
        return Response(request_payload(req, request, with_attendees=True))


@api_view(["GET"])
@permission_classes([IsOperator])
def cabinet(request):
    """Кабинет оператора (`/application/`): его мероприятия и его заявки."""
    user = request.user
    start = date.today()
    events = (
        get_operator_events(user)
        .filter(date_end__range=[start, start + timedelta(days=CABINET_DAYS)])
        .order_by("date_start", "id")
    )
    try:
        requests_qs = owned_requests(user).select_related("event").order_by("-date_created")
    except PermissionDenied:
        requests_qs = Request.objects.none()
    requests_qs = requests_qs.annotate(attendee_count=Count("attendee"))
    lang = request.query_params.get("lang", "ru")
    name_field = {"kz": "name_kaz", "en": "name_eng"}.get(lang, "name_rus")
    cities = {c.city_code: (getattr(c, name_field) or c.name_rus) for c in City.objects.all()}
    returned = (
        Attendee.objects.filter(request__in=requests_qs.values("pk"), status="draft", return_count__gt=0)
        .exclude(review_comment="")
        .values("request_id")
        .annotate(n=Count("id"))
    )
    returned_by_request = {row["request_id"]: row["n"] for row in returned}
    return Response(
        {
            "events": [dict(event_brief(e), city_name=cities.get(e.city_code, "")) for e in events],
            "requests": [
                {
                    "id": r.id,
                    "name": r.name,
                    "status": r.status,
                    "event_id": r.event_id,
                    "date_created": r.date_created,
                    "attendee_count": r.attendee_count,
                    "returned_count": returned_by_request.get(r.id, 0),
                }
                for r in requests_qs
            ],
        }
    )


def attendee_rows(req, request):
    """Участники заявки в порядке страницы заявки (новые сверху, как после добавления)."""
    attendees = Attendee.objects.filter(request=req).select_related("category").order_by("-dateAdd", "-id")
    return AttendeeSerializer(attendees, many=True, context={"request": request}).data


__all__ = ["RequestViewSet", "cabinet", "attendee_rows", "Event"]
