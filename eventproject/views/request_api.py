"""FE-1 — read-only список Request (`/api/v1/requests/`) для селектора формы участника.

`Attendee.request` — FK на Request; форма выбирает Request из RBAC-scoped списка
(тот же `get_operator_events`, что и AttendeeViewSet) вместо ручного ввода PK.
"""

from rest_framework import viewsets

from eventproject.models import Request
from eventproject.permissions import IsOperator
from eventproject.serializers.rbac import get_operator_events
from eventproject.serializers.request import RequestSerializer


class RequestViewSet(viewsets.ReadOnlyModelViewSet):
    """RBAC-scoped список Request для выбора «категории» при создании участника.

    Read-only: оператор только ВЫБИРАЕТ существующий Request своего события
    (создание Request — отдельный флоу). get_queryset скоупит по событиям оператора,
    поэтому чужие Request не видны (паритет с AttendeeViewSet).
    """

    permission_classes = [IsOperator]
    serializer_class = RequestSerializer

    def get_queryset(self):
        events = get_operator_events(self.request.user)
        return (
            Request.objects.filter(event__in=events)
            .select_related("event")
            .order_by("event_id", "id")
        )
