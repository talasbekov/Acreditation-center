"""Этап C: решение проверяющего по участнику (причина возврата, кто и когда).

Существующие участники получают пустую причину и NULL в reviewed_at/by.
Откат: migrate eventproject 0027.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("eventproject", "0032_exportlog_package"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="attendee",
            name="review_comment",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="attendee",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="attendee",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
