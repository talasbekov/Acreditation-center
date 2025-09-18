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
API_KEY = "QGCBR8eSGglfVlgwRTuIFMf3eU0tQs346hNfzbn7c89emHD1mSi29tolxjzf7TbY983XPksUXWgW15UNiLYXZWBxNhMSnLZTrwIR6MiYgCUi4pbQxaET1VDtVo760M68"
BASE_URL = "https://kazenergy.regist.kz/api/api.php"   # GET по одной анкете
ACK_URL  = "https://kazenergy.regist.kz/api/ack.php"   # POST {"id", "code":2/9, "message"?}

REQUIRED_FIELDS = [
    "surname", "firstname", "post", "countryId",
    "docTypeId", "docNumber",
    "sexId", "visitObjects", "transcription", "dateAdd",
    "birthDate", "docBegin", "docEnd"
]

# ────────────────────  LOGGING  ────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _is_empty(v) -> bool:
    """Пусто: None, '', 'null' (в любом регистре)."""
    if v is None:
        return True
    if isinstance(v, str):
        s = v.strip()
        return s == "" or s.lower() == "null"
    return False


def _data_uri_to_contentfile(data_uri: str, filename_stem: str):
    """
    Превращает data URI 'data:image/*;base64,...' в Django ContentFile.
    Возвращает None, если не удаётся декодировать.
    """
    if not data_uri:
        return None

    header = ""
    b64 = ""
    if "," in data_uri:
        header, b64 = data_uri.split(",", 1)
    else:
        b64 = data_uri

    # По заголовку определим расширение (jpeg/jpg/png/webp)
    ext = "jpg"
    if header.startswith("data:") and ";base64" in header:
        try:
            mime = header[5:].split(";")[0].lower()  # image/jpeg
            if "/" in mime:
                sub = mime.split("/")[1]
                if sub in ("jpeg", "jpg", "png", "webp"):
                    ext = "jpg" if sub in ("jpeg", "jpg") else sub
        except Exception:
            pass

    # Удалим пробелы/переносы, выровняем паддинг
    b64_clean = "".join(b64.split())
    rem = len(b64_clean) % 4
    if rem:
        b64_clean += "=" * (4 - rem)

    try:
        raw = base64.b64decode(b64_clean)
        if not raw:
            return None
    except Exception:
        return None

    return ContentFile(raw, name=f"{filename_stem}.{ext}")


@csrf_exempt
async def kazenergy_receive(request, event_id: int, operator_id: int):

    if request.method != "GET":
        return JsonResponse({"error": "Only GET allowed"}, status=405)

    # 1) Event и Operator (для связи с Request)
    try:
        event = await sync_to_async(Event.objects.get)(pk=event_id)
        operator = await sync_to_async(Operator.objects.get)(pk=operator_id)
    except (Event.DoesNotExist, Operator.DoesNotExist):
        return JsonResponse({"error": "Bad event/operator id"}, status=404)

    # 2) Request (повторно используем ≤ 1 часа)
    now = timezone.now()
    last_req = await sync_to_async(
        lambda: Request.objects.filter(event=event, created_by=operator)
        .order_by("-registration_time").first()
    )()
    if not last_req or (now - last_req.registration_time) > timedelta(hours=1):
        req = Request(
            name=now.strftime("%Y%m%d%H%M%S"),
            event=event,
            status="Active",
            created_by=operator,
            registration_time=now,
        )
        await sync_to_async(req.save)()
    else:
        req = last_req

    headers_get  = {"x-api-key": API_KEY}
    headers_post = {"x-api-key": API_KEY, "Content-Type": "application/json"}

    processed = 0
    errors = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            # 3) Забрать одну анкету
            try:
                resp = await client.get(BASE_URL, headers=headers_get)
            except Exception as e:
                logger.error("GET failed: %s", e)
                return JsonResponse({"error": "Upstream GET failed"}, status=502)

            if resp.status_code != 200:
                logger.error("GET %s returned HTTP %s: %s",
                             BASE_URL, resp.status_code, resp.text[:400])
                return JsonResponse({"error": "Upstream error"}, status=502)

            payload = resp.json()
            attendees = payload.get("attendees") or []
            if not attendees:
                logger.info("No attendees (empty queue) — stop")
                break  # важно: выходим из цикла

            attendee = attendees[0]
            attendee_id = attendee.get("id")
            processed += 1

            logger.info("ID=%s  IIN=%s  %s %s",
                        attendee_id,
                        attendee.get("iin"),
                        attendee.get("firstname"),
                        attendee.get("surname"))

            # 4) Валидация обязательных полей
            missing = [f for f in REQUIRED_FIELDS if _is_empty(attendee.get(f))]
            if missing:
                msg = "Отсутствуют поля: " + ", ".join(missing)
                try:
                    # Код ошибки — 9 (ошибка)
                    ack = await client.post(ACK_URL, headers=headers_post,
                                            json={"id": attendee_id, "code": 9, "message": msg})
                    logger.error("ACK error id=%s → %s %s",
                                 attendee_id, ack.status_code, ack.text[:200])
                except Exception as e:
                    logger.error("ACK post failed (error) id=%s: %s", attendee_id, e)
                errors += 1
                continue

            # 5) Дубликат (по transcription)
            dup = await sync_to_async(
                lambda: Attendee.objects.filter(
                    transcription=attendee.get("transcription"),
                    request__event=event
                ).exists()
            )()
            if dup:
                try:
                    # Считаем дубликат «успешно обработанным», чтобы API не отдавал его снова
                    ack = await client.post(ACK_URL, headers=headers_post,
                                            json={"id": attendee_id, "code": 2})
                    logger.info("ACK success (dup) id=%s → %s %s",
                                attendee_id, ack.status_code, ack.text.strip())
                except Exception as e:
                    logger.error("ACK post failed (dup) id=%s: %s", attendee_id, e)
                continue

            # 6) Сохранение в БД
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
                    docSeries=attendee.get("docSeries", ""),  # бывает пусто — ок
                    iin=attendee.get("iin"),                  # бывает пусто — ок
                    docNumber=attendee["docNumber"],
                    docBegin=db,
                    docEnd=de,
                    docIssue=attendee.get("docIssue", ""),    # бывает пусто — ок
                    sexId=attendee["sexId"],
                    dateAdd=da,
                    visitObjects=attendee["visitObjects"],
                    transcription=attendee["transcription"],
                    request=req,
                    dateEnd=de,
                    stickId=attendee.get("stickId", "")       # не понял, что за поле
                )

                # Фото/сканы
                for fld in ("photo", "docScan"):
                    b64 = attendee.get(fld)
                    if b64:
                        cf = _data_uri_to_contentfile(b64, f"{attendee.get('iin') or 'att'}_{fld}")
                        if cf:
                            setattr(att, fld, cf)

                await sync_to_async(att.save)()

                # 7) ACK успех (код 2)
                try:
                    ack = await client.post(ACK_URL, headers=headers_post,
                                            json={"id": attendee_id, "code": 2})
                    logger.info("ACK success id=%s → %s %s",
                                attendee_id, ack.status_code, ack.text.strip())
                except Exception as e:
                    logger.error("ACK post failed (success) id=%s: %s", attendee_id, e)

            except Exception as e:
                # обычные Pg-ошибки, дублируем логику старого блока
                cols = re.findall(r'null value in column "([^"]+)"', str(e))
                if cols:
                    err_msg = ", ".join(f'null value in column "{c}"' for c in cols)
                else:
                    err_msg = str(e).split("DETAIL:")[0].strip()

                logger.error("save-error id=%s iin=%s %s %s: %s",
                             attendee_id,
                             attendee.get("iin"),
                             attendee.get("firstname"),
                             attendee.get("surname"),
                             err_msg)
                try:
                    ack = await client.post(ACK_URL, headers=headers_post,
                                            json={"id": attendee_id, "code": 9, "message": err_msg})
                    logger.error("ACK error id=%s → %s %s",
                                 attendee_id, ack.status_code, ack.text[:200])
                except Exception as e2:
                    logger.error("ACK post failed (error) id=%s: %s", attendee_id, e2)

                errors += 1
                continue

    http_status = 200 if errors == 0 else 400
    logger.info("END import request_id=%s processed=%d errors=%d → HTTP %s",
                req.pk, processed, errors, http_status)

    return JsonResponse(
        {"processed": processed, "errors": errors, "request_id": req.pk},
        status=http_status
    )
