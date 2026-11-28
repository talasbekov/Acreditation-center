"""Саморегистрация по ссылке и регистрация из внешних систем по API-токену (второй этап).

Оператор:
* `events/<id>/registration-links/` GET / POST {link_type: single|multi, count};
  `registration-links/<id>/` DELETE — отключить ссылку;
* `events/<id>/api-tokens/` GET / POST {name} (токен показывается один раз);
  `api-tokens/<id>/` DELETE — отключить токен.

Без входа в систему:
* `public/register/<token>/` GET — мероприятие, доп. поля, справочники; POST — анкета;
* `external/events/<id>/attendees/` POST с `Authorization: Bearer <токен>`.

Участник попадает черновиком в заявку оператора (`Request.source` self_registration / api)
теми же проверками, что форма оператора (AttendeeSerializer): даты, ИИН, дубли,
файлы, доп. поля. Если оператор эту заявку уже отправил, заводится новая.
"""

import hashlib
import json
import secrets

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from directories.models import Category as Stick, Country, DocumentType, Sex
from eventproject.audit import audit_log
from eventproject.errors import coded_error
from eventproject.models import ApiToken, Attendee, CustomField, Event, Operator, RegistrationLink, Request
from eventproject.permissions import IsOperator
from eventproject.serializers.attendee import AttendeeSerializer, raise_if_duplicate
from eventproject.serializers.event import event_brief
from eventproject.serializers.rbac import get_operator_events
from eventproject.services import intake, lifecycle
from eventproject.services.custom_fields import field_payload

MAX_SINGLE_LINKS = 500
PUBLIC_RATE = "30/h"


def _ip(request):
    return request.META.get("REMOTE_ADDR", "")


def _operator(user):
    try:
        return user.operator
    except Operator.DoesNotExist:
        raise coded_error("operator_profile_required")


def _new_request(event, operator, source):
    now = timezone.now()
    return Request.objects.create(
        name=now.strftime("%d%m%Y%H%M%S"), event=event, status=lifecycle.REQUEST_ACTIVE, date_created=now,
        created_by=operator, registration_time=now, source=source,
    )


def _open_request(owner):
    """Заявка для новых участников ссылки/токена; отправленную заменяем новой."""
    req = owner.request
    if not lifecycle.can_add_to(req):
        req = _new_request(owner.event, owner.created_by, req.source)
        owner.request = req
        owner.save(update_fields=["request"])
    return req


def _payload(request_data, req_pk):
    data = {key: request_data.get(key) for key in request_data.keys()}
    raw = data.get("custom_field_values")
    if isinstance(raw, str):
        try:
            data["custom_field_values"] = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            raise coded_error("invalid", field="custom_field_values")
    data["request"] = req_pk
    for field in ("photo", "docScan"):
        if data.get(field) == "":
            data.pop(field)
    return data


def _save_attendee(data, event_id, *, require_files, actor=None, ip="", source="", owner_id=None):
    if require_files:
        for field in ("photo", "docScan"):
            if not data.get(field):
                raise coded_error("required", field=field)
    serializer = AttendeeSerializer(data=data, context={})
    serializer.is_valid(raise_exception=True)
    with intake.event_intake(event_id):
        raise_if_duplicate(event_id, serializer.validated_data)
        attendee = serializer.save(dateAdd=timezone.now())
    audit_log(
        user=actor, action="attendee.create", obj_type="Attendee", obj_id=str(attendee.pk), ip=ip,
        extra={"source": source, "owner": owner_id},
    )
    return attendee


# ── Ссылки саморегистрации (оператор) ─────────────────────────────────────────


def _link_row(link):
    return {
        "id": link.id,
        "token": link.token,
        "url": f"/register/{link.token}",
        "link_type": link.link_type,
        "is_used": link.is_used,
        "is_active": link.is_active,
        "is_available": link.is_available,
        "used_count": link.used_count,
        "request_id": link.request_id,
        "created_at": link.created_at,
        "created_by": link.created_by.user.get_full_name() or link.created_by.user.username,
    }


def _visible(qs, user):
    if user.role in ("superoperator", "superuser"):
        return qs
    return qs.filter(created_by__user=user)


@api_view(["GET", "POST"])
@permission_classes([IsOperator])
def registration_links(request, event_id):
    event = get_object_or_404(get_operator_events(request.user), pk=event_id)
    if request.method == "GET":
        qs = _visible(RegistrationLink.objects.filter(event=event), request.user).select_related("created_by__user")
        return Response({"results": [_link_row(link) for link in qs.order_by("-created_at", "-id")]})

    operator = _operator(request.user)
    link_type = request.data.get("link_type")
    if link_type not in ("single", "multi"):
        raise coded_error("invalid_choice", field="link_type")
    try:
        count = int(request.data.get("count") or 1) if link_type == "single" else 1
    except (TypeError, ValueError):
        raise coded_error("param_not_int", field="count")
    if not 1 <= count <= MAX_SINGLE_LINKS:
        raise coded_error("link_count_invalid", field="count", max=MAX_SINGLE_LINKS)
    with transaction.atomic():
        req = _new_request(event, operator, "self_registration")
        links = [
            RegistrationLink.objects.create(
                event=event, request=req, created_by=operator, token=secrets.token_urlsafe(24), link_type=link_type,
            )
            for _ in range(count)
        ]
    audit_log(
        user=request.user, action="registration_link.create", obj_type="Event", obj_id=str(event.pk), ip=_ip(request),
        extra={"type": link_type, "count": count, "request": req.pk},
    )
    return Response({"results": [_link_row(link) for link in links]}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsOperator])
def registration_link_detail(request, link_id):
    link = get_object_or_404(
        _visible(RegistrationLink.objects.filter(event__in=get_operator_events(request.user)), request.user), pk=link_id
    )
    link.is_active = False
    link.save(update_fields=["is_active"])
    audit_log(user=request.user, action="registration_link.disable", obj_type="RegistrationLink", obj_id=str(link.pk), ip=_ip(request))
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── Публичная форма саморегистрации ───────────────────────────────────────────


def _directories(lang):
    field = {"kz": "name_kaz", "en": "name_eng"}.get(lang, "name_rus")

    def rows(qs, code):
        return [
            {"code": c, "name": (n or "").strip() or ru}
            for c, n, ru in qs.order_by("name_rus").values_list(code, field, "name_rus")
        ]

    return {
        "sexes": rows(Sex.objects.all(), "sex_code"),
        "document_types": rows(DocumentType.objects.all(), "doc_code"),
        "categories": rows(Stick.objects.all(), "category_code"),
        "countries": rows(Country.objects.all(), "country_code"),
    }


def _gone():
    return Response({"type": "link_unavailable", "is_available": False, "detail": "Ссылка недействительна или уже использована."}, status=410)


@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def public_register(request, token):
    link = RegistrationLink.objects.select_related("event").filter(token=token).first()
    if link is None:
        return Response({"type": "not_found", "detail": "Не найдено."}, status=404)
    if request.method == "GET":
        if not link.is_available:
            return _gone()
        lang = request.query_params.get("lang", "ru")
        return Response(
            {
                "event": event_brief(link.event),
                "link_type": link.link_type,
                "is_available": True,
                "custom_fields": [field_payload(f) for f in CustomField.objects.filter(event=link.event)],
                "directories": _directories(lang),
                "kz_country_id": str(getattr(settings, "KZ_COUNTRY_ID", "1000000105")),
            }
        )

    from django_ratelimit.core import is_ratelimited

    if is_ratelimited(request._request, group="public-register", key="ip", rate=PUBLIC_RATE, increment=True):
        return Response({"type": "rate_limited", "detail": "Too many requests."}, status=429)
    with transaction.atomic():
        link = RegistrationLink.objects.select_for_update().select_related("event", "created_by").get(pk=link.pk)
        if not link.is_available:
            return _gone()
        req = _open_request(link)
        attendee = _save_attendee(
            _payload(request.data, req.pk), link.event_id, require_files=True, ip=_ip(request),
            source="self_registration", owner_id=link.pk,
        )
        link.used_count += 1
        if link.link_type == "single":
            link.is_used = True
        link.save(update_fields=["used_count", "is_used"])
    return Response({"id": attendee.pk, "message": "Регистрация принята"}, status=status.HTTP_201_CREATED)


# ── API-токены и внешний эндпоинт ─────────────────────────────────────────────


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_row(t):
    return {
        "id": t.id,
        "name": t.name,
        "token_prefix": t.token_prefix,
        "is_active": t.is_active,
        "last_used_at": t.last_used_at,
        "created_at": t.created_at,
        "request_id": t.request_id,
        "endpoint": f"/api/v1/external/events/{t.event_id}/attendees/",
        "created_by": t.created_by.user.get_full_name() or t.created_by.user.username,
    }


@api_view(["GET", "POST"])
@permission_classes([IsOperator])
def api_tokens(request, event_id):
    event = get_object_or_404(get_operator_events(request.user), pk=event_id)
    if request.method == "GET":
        qs = _visible(ApiToken.objects.filter(event=event), request.user).select_related("created_by__user")
        return Response({"results": [_token_row(t) for t in qs.order_by("-created_at", "-id")]})
    operator = _operator(request.user)
    name = str(request.data.get("name") or "").strip()[:255]
    token = "acc_" + secrets.token_urlsafe(32)
    with transaction.atomic():
        req = _new_request(event, operator, "api")
        row = ApiToken.objects.create(
            event=event, request=req, created_by=operator, name=name, token_prefix=token[:10], token_hash=_hash(token),
        )
    audit_log(user=request.user, action="api_token.create", obj_type="ApiToken", obj_id=str(row.pk), ip=_ip(request))
    return Response(dict(_token_row(row), token=token), status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsOperator])
def api_token_detail(request, token_id):
    row = get_object_or_404(_visible(ApiToken.objects.filter(event__in=get_operator_events(request.user)), request.user), pk=token_id)
    row.is_active = False
    row.save(update_fields=["is_active"])
    audit_log(user=request.user, action="api_token.disable", obj_type="ApiToken", obj_id=str(row.pk), ip=_ip(request))
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def external_attendees(request, event_id):
    """Регистрация участника внешней системой: `Authorization: Bearer <токен>`."""
    header = request.META.get("HTTP_AUTHORIZATION", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    row = ApiToken.objects.filter(token_hash=_hash(token), is_active=True).select_related("event").first() if token else None
    if row is None or row.event_id != int(event_id):
        return Response({"type": "not_authenticated", "detail": "Неверный или отключённый токен."}, status=401)
    get_object_or_404(Event, pk=event_id)
    with transaction.atomic():
        row = ApiToken.objects.select_for_update().select_related("created_by").get(pk=row.pk)
        req = _open_request(row)
        attendee = _save_attendee(
            _payload(request.data, req.pk), row.event_id, require_files=False, ip=_ip(request), source="api", owner_id=row.pk,
        )
        row.last_used_at = timezone.now()
        row.save(update_fields=["last_used_at"])
    return Response({"id": attendee.pk, "status": attendee.status, "request": req.pk}, status=status.HTTP_201_CREATED)


__all__ = ["Attendee"]
