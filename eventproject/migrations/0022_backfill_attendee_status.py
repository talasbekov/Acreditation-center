from django.db import migrations

# Story 4.3 (Задача 0): backfill Attendee.status из Request.status.
# Миграция 0020 проставила всем `draft` → delta-export (status=ready) выгрузил бы ноль.
# Маппинг утверждён Project Lead (Erda) 2026-06-23. Неизвестные/пустые Request.status
# остаются `draft` (fail-safe; они уже draft после 0020 — отдельно не трогаем).
_STATUS_MAP = {
    "Active": "draft",
    "Checking": "in_review",
    "Sent": "ready",
    "Exported": "exported",
    "completed": "exported",
}


def backfill_status(apps, schema_editor):
    Attendee = apps.get_model("eventproject", "Attendee")
    for request_status, attendee_status in _STATUS_MAP.items():
        Attendee.objects.filter(request__status=request_status).update(
            status=attendee_status
        )


class Migration(migrations.Migration):

    dependencies = [
        ("eventproject", "0021_normalize_blank_iin"),
    ]

    operations = [
        migrations.RunPython(backfill_status, migrations.RunPython.noop),
    ]
