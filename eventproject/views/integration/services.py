# myapp/services.py
import base64
import uuid
from django.core.files.base import ContentFile
from django.utils.dateparse import parse_date, parse_datetime
from asgiref.sync import sync_to_async

from eventproject.models import Attendee, Request

async def process_avalon_payload(payload, event, operator):
    """
    Создаёт Request, сохраняет список attendees и возвращает его id и список созданных attendee_ids.
    """
    # 1) создаём Request
    req = await sync_to_async(Request.objects.create)(
        event=event,
        status="processing",
        created_by=operator,
    )

    created_ids = []
    for data in payload.get("attendees", []):
        bd = parse_date(data.get("birthDate"))    if data.get("birthDate") else None
        da = parse_datetime(data.get("dateAdd"))  if data.get("dateAdd")   else None
        db = parse_date(data.get("docBegin"))     if data.get("docBegin") else None
        de = parse_date(data.get("docEnd"))       if data.get("docEnd")   else None

        attendee = Attendee(
            surname       = data.get("surname",""),
            firstname     = data.get("firstname",""),
            patronymic    = data.get("patronymic","") or "",
            birthDate     = bd,
            post          = data.get("post",""),
            countryId     = data.get("countryId",""),
            docTypeId     = data.get("docTypeId",""),
            docSeries     = data.get("docSeries","") or "",
            iin           = data.get("iin",""),
            docNumber     = data.get("docNumber",""),
            docBegin      = db,
            docEnd        = de,
            docIssue      = data.get("docIssue",""),
            sexId         = data.get("sexId",""),
            dateAdd       = da,
            visitObjects  = data.get("visitObjects",""),
            transcription = data.get("transcription",""),
            request       = req,
            dateEnd       = de,
            stickId       = data.get("stickId",""),
        )

        # base64 → ImageField
        for fld in ("photo", "docScan"):
            b64 = data.get(fld)
            if b64:
                if "," in b64:
                    header, b64 = b64.split(",", 1)
                    ext = header.split("/")[1].split(";")[0]
                else:
                    ext = "jpg"
                # L2: НЕ кладём IIN (PII) в имя файла — иначе шифрование колонки
                # iin обесценивается для любого, кто видит media. Берём id записи
                # от Avalon (как в kazenergy-пути), иначе случайный токен.
                stem = data.get("id") or uuid.uuid4().hex
                name = f"{stem}_{fld}.{ext}"
                content = ContentFile(base64.b64decode(b64), name=name)
                setattr(attendee, fld, content)

        await sync_to_async(attendee.save)()
        created_ids.append(attendee.pk)

    # помечаем Request как завершённый
    req.status = "completed"
    req.exported_by = operator
    await sync_to_async(req.save)()

    return req.pk, created_ids
