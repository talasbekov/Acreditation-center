"""Импорт анкет KazEnergy (вызывается по расписанию из eventproject.cron).

Приём идемпотентен и общий с Avalon — см. ``eventproject.services.partner_import``.
"""

import logging

import httpx
from asgiref.sync import sync_to_async
from django.conf import settings as django_settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from eventproject.models import Event, Operator
from eventproject.services import partner_import

API_KEY = django_settings.KAZENERGY_API_KEY
BASE_URL = "https://kazenergy.regist.kz/api/api.php"   # GET по одной анкете
ACK_URL = "https://kazenergy.regist.kz/api/ack.php"    # POST {"id", "code":2/9, "message"?}

logger = logging.getLogger(__name__)


@csrf_exempt
async def kazenergy_receive(request, event_id: int, operator_id: int):
    if request.method != "GET":
        return JsonResponse({"error": "Only GET allowed"}, status=405)

    if not API_KEY:
        return JsonResponse({"error": "Partner credentials are not configured"}, status=503)

    try:
        event = await sync_to_async(Event.objects.get)(pk=event_id)
        operator = await sync_to_async(Operator.objects.get)(pk=operator_id)
    except (Event.DoesNotExist, Operator.DoesNotExist):
        return JsonResponse({"error": "Bad event/operator id"}, status=404)

    async with httpx.AsyncClient(timeout=30.0) as client:
        result = await partner_import.run(
            partner_import.KAZENERGY, event, operator, client,
            get_url=BASE_URL, ack_url=ACK_URL,
            headers_get={"x-api-key": API_KEY},
            headers_post={"x-api-key": API_KEY, "Content-Type": "application/json"},
        )

    if result.upstream_failed and not result.processed:
        return JsonResponse({"error": "Upstream error"}, status=502)
    http_status = 200 if result.errors == 0 else 400
    logger.info("Partner import finished processed=%d errors=%d status=%d",
                result.processed, result.errors, http_status)
    return JsonResponse(result.payload(), status=http_status)
