"""Общие хелперы legacy function-based вью (RU/KZ/EN)."""

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from eventproject.models import Attendee, Operator, Request
from eventproject.serializers.rbac import get_operator_events


def require_operator(user):
    """A signed-in user needs an operator profile to own a request."""
    if not user.is_authenticated:
        raise PermissionDenied
    try:
        return user.operator
    except Operator.DoesNotExist:
        raise PermissionDenied("Требуется профиль оператора")


def assigned_event(user, event_id):
    return get_object_or_404(get_operator_events(user), pk=event_id)


def owned_requests(user):
    return Request.objects.filter(created_by=require_operator(user), event__in=get_operator_events(user))


def owned_request(user, request_id):
    return get_object_or_404(owned_requests(user), pk=request_id)


def owned_attendee(user, attendee_id):
    attendees = Attendee.objects.select_related("request").filter(request__in=owned_requests(user))
    return get_object_or_404(attendees, pk=attendee_id)
