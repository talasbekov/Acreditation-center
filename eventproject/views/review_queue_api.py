"""Story fe-3.1 — DRF ReviewQueueViewSet (`GET /api/v1/review-queue/`).

Scope-aware очередь проверки админа: read-only агрегат заявок «на рассмотрении»
(submitted + in_review — прецедент dashboard.py). Замораживает исполняемый контракт
DTO (ReviewQueueSerializer) для UI 3.2-3.7. RBAC — IsSuperoperator (admin-агрегат).
Scope НАСЛЕДУЕТСЯ от get_operator_attendee_queryset (hd-5.3) — не переизобретается.
"""

from django.db.models import TextField
from django.db.models.functions import Cast
from rest_framework import viewsets
from rest_framework.filters import SearchFilter

from eventproject.errors import coded_error
from eventproject.permissions import IsSuperoperator
from eventproject.problem_flags import is_valid_problem_flag
from eventproject.serializers.rbac import get_operator_attendee_queryset
from eventproject.serializers.review_queue import (
    ReviewQueueDetailSerializer,
    ReviewQueueSerializer,
)
from eventproject.state_machine import AttendeeStatus

# Очередь проверки = заявки на рассмотрении (submitted + in_review).
# Прецедент: eventproject/views/dashboard.py — "review" = submitted + in_review.
_REVIEW_QUEUE_STATUSES = (AttendeeStatus.SUBMITTED, AttendeeStatus.IN_REVIEW)


class ReviewQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """Очередь проверки админа. List + detail; решения approve/return — 3.4/3.5."""

    permission_classes = [IsSuperoperator]
    serializer_class = ReviewQueueSerializer
    # Поиск по ИМЕНИ (ИИН шифрован → SQL-поиск невозможен). icontains кейс-инсенситивен
    # только на Postgres (prod); тест кириллицы под @skipUnless(postgresql).
    filter_backends = [SearchFilter]
    search_fields = ["surname", "firstname", "patronymic"]

    def get_serializer_class(self):
        # fe-3.3: detail-экран (retrieve) требует фото/скан + identity-поля; список
        # остаётся тонким DTO (не раздуваем очередь). Маск-ИИН наследуется обоими.
        if self.action == "retrieve":
            return ReviewQueueDetailSerializer
        return ReviewQueueSerializer

    def get_queryset(self):
        # Scope НАСЛЕДУЕТСЯ (hd-5.3): не дублируем request__event__in. superoperator/
        # superuser → полный агрегат; фильтруем по статусам очереди.
        qs = (
            get_operator_attendee_queryset(self.request.user)
            .filter(status__in=_REVIEW_QUEUE_STATUSES)
            .select_related("request__event")
            # Стабильный tiebreak `-id`: bulk-импорт даёт одинаковые dateAdd → без
            # вторичного ключа строки переупорядочиваются между страницами (дубли/пропуски).
            .order_by("-dateAdd", "-id")
        )

        # ?sub_event_id= — id leaf-Event (= request.event_id). Не-int/пустой → 400;
        # неизвестный id → пустой список (семантика list-фильтра, НЕ 404).
        sub_event_id = self.request.query_params.get("sub_event_id")
        if sub_event_id is not None:
            try:
                sub_event_id = int(sub_event_id)
            except (TypeError, ValueError):
                raise coded_error("param_not_int", field="sub_event_id")
            qs = qs.filter(request__event_id=sub_event_id)

        # ?problem= — член закрытого набора PROBLEM_FLAGS; вне набора/пустой → 400.
        # Портируемый фильтр по хранимому JSONField: Cast→TextField + icontains по
        # кавыченному значению `"flag"` (jsonb `__contains` не поддержан на SQLite →
        # 500 в dev/CI; Cast-icontains работает на Postgres И SQLite). Значение уже
        # провалидировано closed-set'ом выше → инъекции нет; кавычки исключают
        # ложные совпадения (ни один флаг не подстрока кавыченного другого).
        problem = self.request.query_params.get("problem")
        if problem is not None:
            if not is_valid_problem_flag(problem):
                raise coded_error("problem_invalid", field="problem")
            qs = qs.annotate(
                _pf_text=Cast("problem_flags", output_field=TextField())
            ).filter(_pf_text__icontains=f'"{problem}"')

        # ?status= — опц. сужение ВНУТРИ очереди (только submitted|in_review).
        status_param = self.request.query_params.get("status")
        if status_param is not None:
            if status_param not in _REVIEW_QUEUE_STATUSES:
                raise coded_error("status_invalid", field="status")
            qs = qs.filter(status=status_param)

        return qs
