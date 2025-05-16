import base64
import logging
import re
from datetime import timedelta

import httpx
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.csrf import csrf_exempt

from eventproject.models import Attendee, Event, Operator, Request

# ────────────────────  CONSTANTS  ────────────────────
AVALON_API_KEY = (
    "Fe6dv1LkLMpY0pqwSuocznfwyGo77upgHYfobtPDM98REHKMWXmW3KW6WKbYZ2t5Q2Fd515wPhIVp"
    "YaYt1zRghD3mDB6EQ04XzSD6meoAWVdvZT5vrfM6vCPumCzr55hh"
)
AVALON_BASE = (
    "https://avalon.kazintec.kz/api/v1/events/"
    "2b98b904-3a1b-422c-99bc-71ffe69b01d4/export"
)
AVALON_ACK_URL = AVALON_BASE

# Все поля, которые должны быть НЕ-пустыми
REQUIRED_FIELDS = [
    "surname", "firstname", "post", "countryId",
    "docTypeId", "docSeries", "docNumber", "docIssue",
    "sexId", "visitObjects", "transcription", "dateAdd",
    "birthDate", "docBegin", "docEnd", "stickId"
]

# ────────────────────  LOGGING  ────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@csrf_exempt
async def kazexpo_receive(request, event_id: int, operator_id: int):
    if request.method != "GET":
        return JsonResponse({"error": "Only GET allowed"}, status=405)

    # 1. Получаем Event и Operator ------------------------------------------------
    try:
        event = await sync_to_async(Event.objects.get)(pk=event_id)
        operator = await sync_to_async(Operator.objects.get)(pk=operator_id)
    except (Event.DoesNotExist, Operator.DoesNotExist):
        return JsonResponse({"error": "Bad event/operator id"}, status=404)

    # 2. Request (повторно используем ≤1 ч) --------------------------------------
    now = timezone.now()
    last_req = await sync_to_async(
        lambda: Request.objects
        .filter(event=event, created_by=operator)
        .order_by("-registration_time").first()
    )()
    if not last_req or (now - last_req.registration_time) > timedelta(hours=1):
        req = Request(name=now.strftime("%Y%m%d%H%M%S"),
                      event=event, status="Active",
                      created_by=operator, registration_time=now)
        await sync_to_async(req.save)()
    else:
        req = last_req

    headers_get = {"x-api-key": AVALON_API_KEY}
    headers_post = {"x-api-key": AVALON_API_KEY,
                    "Content-Type": "application/json"}

    processed = 0
    errors = 0

    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(AVALON_BASE, headers=headers_get)

            if resp.status_code in (404, 500):
                break
            if resp.status_code != 200:
                return JsonResponse({"error": "Avalon error"}, status=502)

            # ───── 1. JSON берём ОДИН раз ─────
            payload = resp.json()
            arr = payload.get("attendees") or []
            if not arr:
                logger.warning("Empty attendee payload, skipping")
                continue
            attendee = arr[0]
            attendee_id = attendee.get("id")
            processed += 1
            logger.info("ID=%s  IIN=%s  %s %s",
                        attendee_id,
                        attendee.get("iin"),
                        attendee.get("firstname"),
                        attendee.get("surname"))

            # ───── 2. PRE-VALIDATION ─────
            def is_empty(v):
                return (
                        v is None
                        or (isinstance(v, str) and not v.strip())
                        or (isinstance(v, str) and v.strip().lower() == "null")
                )

            missing = [f for f in REQUIRED_FIELDS if is_empty(attendee.get(f))]
            if missing:
                err_msg = ", ".join(f'null value in column "{fld}"' for fld in missing)
                logger.error("validation-error ID=%s: %s", attendee_id, err_msg)
                await client.post(
                    AVALON_ACK_URL,
                    headers=headers_post,
                    json={"id": attendee_id, "code": 1, "message": err_msg}
                )
                errors += 1
                continue

            # ───────────────────────────────────────────────────────────────────

            # 4. Дубликат ---------------------------------------------------------
            dup = await sync_to_async(
                lambda: Attendee.objects.filter(
                    transcription=attendee.get("transcription"),
                    request__event=event
                ).exists()
            )()
            if dup:
                await client.post(AVALON_ACK_URL, headers=headers_post,
                                  json={"id": attendee_id, "code": 2})
                continue

            # 6. Сохраняем в БД ---------------------------------------------------
            try:
                bd = parse_date(attendee.get("birthDate"))
                da = parse_datetime(attendee.get("dateAdd"))
                db = parse_date(attendee.get("docBegin"))
                de = parse_date(attendee.get("docEnd"))

                att = Attendee(
                    surname=attendee["surname"],
                    firstname=attendee["firstname"],
                    patronymic=attendee.get("patronymic", ""),
                    birthDate=bd,
                    post=attendee["post"],
                    countryId=attendee["countryId"],
                    docTypeId=attendee["docTypeId"],
                    docSeries=attendee["docSeries"],
                    iin=attendee.get("iin"),
                    docNumber=attendee["docNumber"],
                    docBegin=db,
                    docEnd=de,
                    docIssue=attendee["docIssue"],
                    sexId=attendee["sexId"],
                    dateAdd=da,
                    visitObjects=attendee["visitObjects"],
                    transcription=attendee["transcription"],
                    request=req,
                    dateEnd=de,
                    stickId=attendee.get("stickId", "")
                )

                for fld in ("photo", "docScan"):
                    b64 = attendee.get(fld)
                    if b64:
                        header, data_b64 = b64.split(",", 1) if "," in b64 else ("", b64)
                        ext = header.split("/")[1].split(";")[0] if header else "jpg"
                        setattr(att, fld,
                                ContentFile(base64.b64decode(data_b64),
                                            name=f"{att.iin or 'att'}_{fld}.{ext}"))

                await sync_to_async(att.save)()

                await client.post(AVALON_ACK_URL, headers=headers_post,
                                  json={"id": attendee_id, "code": 2})

            except Exception as e:
                # обычные Pg-ошибки, дублируем логику старого блока
                cols = re.findall(r'null value in column "([^"]+)"', str(e))
                if cols:
                    err_msg = ", ".join(f'null value in column "{c}"' for c in cols)
                else:
                    err_msg = str(e).split("DETAIL:")[0].strip()

                logger.error("save-error ID=%s IIN=%s %s %s: %s",
                             attendee_id,
                             attendee.get("iin"),
                             attendee.get("firstname"),
                             attendee.get("surname"),
                             err_msg)

                await client.post(AVALON_ACK_URL, headers=headers_post,
                                  json={"id": attendee_id,
                                        "code": 1,
                                        "message": err_msg})
                errors += 1
                continue   # следующий участник

    # 7. Итоговый HTTP статус -----------------------------------------------------
    http_status = 200 if errors == 0 else 400
    logger.info("END import request_id=%s processed=%d errors=%d → HTTP %s",
                req.pk, processed, errors, http_status)

    return JsonResponse({"processed": processed,
                         "errors": errors,
                         "request_id": req.pk},
                        status=http_status)
