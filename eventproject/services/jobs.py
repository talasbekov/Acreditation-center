"""Очередь фоновых задач на PostgreSQL (второй этап).

`enqueue` записывает задачу; воркер (`manage.py run_jobs`) забирает её через
SELECT … FOR UPDATE SKIP LOCKED, поэтому несколько воркеров не возьмут одну задачу.
При `settings.JOBS_RUN_INLINE` задача выполняется сразу после фиксации транзакции
(разработка, тесты).

Типы задач: `badge_pdf` — PDF бейджей мероприятия.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from eventproject.audit import audit_log
from eventproject.models import Attendee, BadgeTemplate, Job

logger = logging.getLogger("eventproject")

# Задача «в работе» дольше этого — воркер, видимо, упал: вернуть в очередь.
STALE_AFTER = timedelta(minutes=30)


def enqueue(job_type, payload, user=None):
    job = Job.objects.create(type=job_type, payload=payload, created_by=user)
    if getattr(settings, "JOBS_RUN_INLINE", False):
        transaction.on_commit(lambda: run(job.pk))
    return job


def claim_next():
    """Взять следующую задачу из очереди (или None)."""
    with transaction.atomic():
        qs = Job.objects.filter(status="pending").order_by("created_at", "id")
        if connection.features.has_select_for_update_skip_locked:
            qs = qs.select_for_update(skip_locked=True)
        job = qs.first()
        if job is None:
            return None
        job.status = "processing"
        job.started_at = timezone.now()
        job.attempts += 1
        job.save(update_fields=["status", "started_at", "attempts"])
        return job


def requeue_stale():
    cutoff = timezone.now() - STALE_AFTER
    return Job.objects.filter(status="processing", started_at__lt=cutoff).update(status="pending")


def run(job_id):
    """Выполнить задачу (уже взятую воркером или поставленную inline)."""
    job = Job.objects.get(pk=job_id)
    if job.status == "pending":
        job.status = "processing"
        job.started_at = timezone.now()
        job.attempts += 1
        job.save(update_fields=["status", "started_at", "attempts"])
    handler = HANDLERS.get(job.type)
    try:
        if handler is None:
            raise RuntimeError(f"unknown job type {job.type}")
        result = handler(job)
    except Exception as exc:  # noqa: BLE001 — любая ошибка задачи не должна ронять воркер
        logger.error("job failed", extra={"obj_type": "Job", "obj_id": str(job.pk)})
        job.error = str(exc)[:1000]
        job.status = "failed" if job.attempts >= job.max_attempts else "pending"
        job.completed_at = timezone.now() if job.status == "failed" else None
        job.save(update_fields=["error", "status", "completed_at"])
        return job
    job.status = "completed"
    job.result = result
    job.progress = 100
    job.completed_at = timezone.now()
    job.error = ""
    job.save(update_fields=["status", "result", "progress", "completed_at", "error", "file_path"])
    return job


def _badge_pdf(job):
    from eventproject.services import badges

    event_id = int(job.payload["event_id"])
    ids = [int(x) for x in job.payload.get("attendee_ids", [])]
    attendees = list(
        Attendee.objects.filter(pk__in=ids, request__event_id=event_id, access_status="yes").order_by("surname", "firstname", "id")
    )
    template = BadgeTemplate.objects.filter(event_id=event_id).first()
    path = badges.private_path("badges", f"event_{event_id}", f"{job.pk}.pdf")
    total = max(1, len(attendees))

    def progress(done):
        Job.objects.filter(pk=job.pk).update(progress=min(99, int(done * 100 / total)))

    with open(path, "wb") as out:
        warnings = badges.build_pdf(attendees, template, out, progress=progress)
    now = timezone.now()
    Attendee.objects.filter(pk__in=[a.pk for a in attendees]).update(badge_printed_at=now)
    job.file_path = str(path)
    audit_log(
        user=job.created_by, action="badge.generated", obj_type="Event", obj_id=str(event_id), ip="",
        extra={"job": job.pk, "count": len(attendees)},
    )
    return {"badge_count": len(attendees), "warnings": warnings, "event_id": event_id, "file_name": f"badges_{event_id}_{job.pk}.pdf"}


HANDLERS = {"badge_pdf": _badge_pdf}
