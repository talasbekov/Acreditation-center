"""Этап C: неизменяемый пакет выгрузки, повторная выдача и подтверждение получателя.

Существующим записям присваивается собственный package_id. Их состав не
записывался, поэтому attendee_ids/manifest остаются NULL и повторная выдача для
них недоступна. Откат: migrate eventproject 0026 удаляет новые поля без потери
прежних данных ExportLog.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def assign_package_ids(apps, schema_editor):
    logs = apps.get_model("eventproject", "ExportLog").objects.using(schema_editor.connection.alias)
    for log_id in logs.filter(package_id__isnull=True).values_list("pk", flat=True).iterator():
        logs.filter(pk=log_id).update(package_id=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [
        ("eventproject", "0026_backfill_legacy_event_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="exportlog",
            name="package_id",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(assign_package_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="exportlog",
            name="package_id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, unique=True,
                help_text="Неизменяемый идентификатор пакета выгрузки",
            ),
        ),
        migrations.AlterField(
            model_name="exportlog",
            name="exported_before",
            field=models.DateTimeField(help_text="Момент формирования пакета"),
        ),
        migrations.AddField(
            model_name="exportlog",
            name="attendee_ids",
            field=models.JSONField(blank=True, null=True, help_text="Упорядоченный список ID участников пакета"),
        ),
        migrations.AddField(
            model_name="exportlog",
            name="manifest",
            field=models.JSONField(blank=True, null=True, help_text="SHA-256 каждого элемента архива: {имя в ZIP: hex}"),
        ),
        migrations.AddField(
            model_name="exportlog",
            name="archive_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="exportlog",
            name="archive_sha256",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="exportlog",
            name="acknowledged_at",
            field=models.DateTimeField(blank=True, null=True, help_text="Когда получатель подтвердил приём пакета"),
        ),
        migrations.AddField(
            model_name="exportlog",
            name="acknowledged_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to=settings.AUTH_USER_MODEL,
                help_text="Кто отметил подтверждение получателя",
            ),
        ),
    ]
