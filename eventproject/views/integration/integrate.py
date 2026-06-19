import asyncio
import base64
import logging
import csv
import os
from django.conf import settings
from datetime import timedelta
import httpx
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from django.conf import settings as django_settings
from eventproject.models import Attendee, Event, Operator, Request
from eventproject.validators.iin import event_has_iin_duplicate, mask_iin, normalize_iin

# ────────────────────  CONSTANTS  ────────────────────
AVALON_API_KEY = django_settings.AVALON_API_KEY
AVALON_BASE = (
    "https://avalon.kazintec.kz/api/v1/events/"
    "2b98b904-3a1d-422c-99bc-71gge69b01d4/export"
)
AVALON_ACK_URL = AVALON_BASE

# Все поля, которые должны быть НЕ-пустыми
REQUIRED_FIELDS = [
    "surname", "firstname", "post", "countryId",
    "docTypeId", "sexId", "visitObjects", "transcription",
    "birthDate", "stickId"
]

# ────────────────────  LOGGING  ────────────────────
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def write_csv_header(file_path):
    """
    Создаёт каталог, если надо, и в файл file_path
    в текстовом режиме пишет заголовок CSV.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(['№', 'ID', 'Фамилия', 'Имя', 'IIN'])


def write_csv_row_dict(file_path, idx, attendee_dict):
    with open(file_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            idx,
            attendee_dict.get("id"),
            attendee_dict.get("surname", ""),
            attendee_dict.get("firstname", ""),
            mask_iin(attendee_dict.get("iin")),
        ])


# @csrf_exempt
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

    # 1. Operator берём из сессии, Event — из URL --------------------------------
    try:
        operator = await sync_to_async(Operator.objects.get)(user=user)
    except Operator.DoesNotExist:
        return JsonResponse({"error": "Operator profile required"}, status=403)

    if not (user.is_superuser or operator.role in ("superoperator", "superuser")):
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        event = await sync_to_async(Event.objects.get)(pk=event_id)
    except Event.DoesNotExist:
        return JsonResponse({"error": "Bad event id"}, status=404)

    if not user.is_superuser:
        is_bound = await sync_to_async(operator.events.filter(pk=event_id).exists)()
        if not is_bound:
            return JsonResponse({"error": "Not authorized for this event"}, status=403)

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

    # — подготовить путь и заголовок CSV-файла
    now = timezone.localtime(timezone.now())
    filename = now.strftime('%H%M%S_%d%m%Y') + '.csv'
    export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
    file_path = os.path.join(export_dir, filename)

    # синхронную операцию оборачиваем в поток
    await sync_to_async(write_csv_header)(file_path)

    processed = 0
    errors = 0

    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.get(AVALON_BASE, headers=headers_get)

                if resp.status_code in (404, 500):
                    break
                if resp.status_code != 200:
                    return JsonResponse({"error": "Avalon error"}, status=502)

                # ───── 1. JSON берём ОДИН раз ─────
                payload = resp.json()
                arr = payload.get("attendees") or []
                if not arr:
                    logger.warning("Пропущен: пустой payload")
                    break
                attendee = arr[0]
                attendee_id = attendee.get("id")
                processed += 1
                logger.info("#%d - RECORD: ID=%s  IIN=%s",
                            processed,
                            attendee_id,
                            mask_iin(attendee.get("iin")))

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
                    logger.warning("Ошибка обработки участника ID=%s, переход к седующему", attendee_id)
                    continue

                # ───────────────────────────────────────────────────────────────────

                # 4. Дубликат --------------------------------------------
                iin = normalize_iin(attendee.get("iin"))
                transcription = attendee.get("transcription")

                event_qs = Attendee.objects.filter(request__event=event)
                if iin:
                    is_duplicate = await sync_to_async(
                        lambda: event_has_iin_duplicate(event_qs, iin)
                    )()
                    match_field = "iin"
                else:
                    is_duplicate = await sync_to_async(
                        lambda: event_qs.filter(transcription=transcription).exists()
                    )()
                    match_field = "transcription"

                if is_duplicate:
                    logger.warning(
                        "\n=== НАЙДЕН ДУБЛИКАТ ===\nID: %s\nСравнение по: %s\n=====================",
                        attendee_id,
                        match_field,
                    )
                    await client.post(AVALON_ACK_URL, headers=headers_post,
                                      json={"id": attendee_id, "code": 1, "comment": "Дубликат"})
                    logger.info("Дубликат: участник ID=%s, отправлено подтверждение", attendee_id)
                    continue
                await sync_to_async(write_csv_row_dict)(file_path, processed, attendee)

                # 6. Сохраняем в БД ---------------------------------------------------
                try:
                    bd = parse_date(attendee.get("birthDate"))
                    da = parse_datetime(attendee.get("dateAdd") or "")
                    db = parse_date(attendee.get("docBegin") or "")
                    de = parse_date(attendee.get("docEnd") or "")

                    att = Attendee(
                        surname=attendee["surname"],
                        firstname=attendee["firstname"],
                        patronymic=attendee["patronymic"] or " ",
                        birthDate=bd,
                        post=attendee["post"],
                        countryId=attendee["countryId"],
                        docTypeId=attendee["docTypeId"],
                        docSeries=attendee["docSeries"] or " ",
                        iin=attendee["iin"] or " ",
                        docNumber=attendee["docNumber"] or " ",
                        docBegin=db,
                        docEnd=de,
                        docIssue=attendee["docIssue"] or " ",
                        sexId=attendee["sexId"],
                        dateAdd=da,
                        visitObjects=attendee["visitObjects"],
                        transcription=attendee["transcription"],
                        request=req,
                        dateEnd=de,
                        stickId=attendee["stickId"]
                    )

                    for fld in ("photo", "docScan"):
                        b64 = attendee.get(fld)
                        if b64:
                            header, data_b64 = b64.split(",", 1) if "," in b64 else ("", b64)
                            ext = header.split("/")[1].split(";")[0] if header else "jpg"
                            setattr(att, fld,
                                    ContentFile(base64.b64decode(data_b64),
                                                name=f"{attendee_id or 'att'}_{fld}.{ext}"))

                    await sync_to_async(att.save)()

                    await client.post(AVALON_ACK_URL, headers=headers_post,
                                      json={"id": attendee_id, "code": 2, "RECORD NUMBER": f"№{processed}"})

                except Exception as e:
                    # обычные Pg-ошибки, дублируем логику старого блока
                    err_msg = str(e)

                    logger.error("save-error ID=%s IIN=%s: %s",
                                 attendee_id,
                                 mask_iin(attendee.get("iin")),
                                 err_msg)

                    await client.post(AVALON_ACK_URL, headers=headers_post,
                                      json={"id": attendee_id,
                                            "code": 1,
                                            "message": "Ошибка при сохранении участника",
                                            "error_detail": err_msg,
                                            "RECORD NUMBER": processed})
                    errors += 1
                    logger.info("Ошибка сохранении участника ID=%s, переход к следующему", attendee_id)
                    continue   # следующий участник
            finally:
                await asyncio.sleep(0.3)

    # 8. Итоговый HTTP статус -----------------------------------------------------
    logger.info("Готовый CSV: %s", file_path)

    http_status = 200 if errors == 0 else 400
    logger.info("END import request_id=%s processed=%d errors=%d → HTTP %s",
                req.pk, processed, errors, http_status)

    return JsonResponse({"processed": processed,
                         "errors": errors,
                         "request_id": req.pk},
                        status=http_status)



