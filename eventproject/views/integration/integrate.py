"""Импорт анкет Avalon (KazExpo) по запросу супероператора.

Приём идемпотентен и общий с KazEnergy — см. ``eventproject.services.partner_import``.
"""

import logging

import httpx
from asgiref.sync import sync_to_async
from django.conf import settings as django_settings
from django.http import JsonResponse

from eventproject.models import Event, Operator
from eventproject.services import partner_import

AVALON_API_KEY = django_settings.AVALON_API_KEY
AVALON_BASE = (
    "https://avalon.kazintec.kz/api/v1/events/"
    "2b98b904-3a1d-422c-99bc-71gge69b01d4/export"
)
AVALON_ACK_URL = AVALON_BASE

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def kazexpo_receive(request, event_id: int):
    # Импорт меняет состояние (создаёт Request/Attendee) → только POST.
    # CSRF обеспечивает CsrfViewMiddleware (view не помечен csrf_exempt).
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    # AuthN/AuthZ — эндпоинт запускает импорт PII из Avalon:
    #   * требуется аутентифицированный пользователь;
    #   * operator берётся из request.user, НЕ из URL (защита от IDOR);
    #   * импорт доступен только супероператору/суперпользователю;
    #   * оператор должен быть привязан к событию (суперпользователь — в обход).
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        operator = await sync_to_async(Operator.objects.get)(user=user)
    except Operator.DoesNotExist:
        return JsonResponse({"error": "Operator profile required"}, status=403)

    if not user.is_superuser and operator.role != "superoperator":
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        event = await sync_to_async(Event.objects.get)(pk=event_id)
    except Event.DoesNotExist:
        return JsonResponse({"error": "Bad event id"}, status=404)

    if not user.is_superuser:
        is_bound = await sync_to_async(operator.events.filter(pk=event_id).exists)()
        if not is_bound:
            return JsonResponse({"error": "Not authorized for this event"}, status=403)

    if not AVALON_API_KEY:
        return JsonResponse({"error": "Partner credentials are not configured"}, status=503)

    async with httpx.AsyncClient() as client:
        result = await partner_import.run(
            partner_import.AVALON, event, operator, client,
            get_url=AVALON_BASE, ack_url=AVALON_ACK_URL,
            headers_get={"x-api-key": AVALON_API_KEY},
            headers_post={"x-api-key": AVALON_API_KEY, "Content-Type": "application/json"},
            stop_statuses=(404, 500), pause=0.3,
        )

    if result.upstream_failed and not result.processed:
        return JsonResponse({"error": "Avalon error"}, status=502)
    http_status = 200 if result.errors == 0 else 400
    logger.info("Partner import finished processed=%d errors=%d status=%d",
                result.processed, result.errors, http_status)
    return JsonResponse(result.payload(), status=http_status)
