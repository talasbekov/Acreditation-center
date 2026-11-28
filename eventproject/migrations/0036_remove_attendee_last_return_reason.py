"""Удаляет дубль причины возврата: остаётся review_comment (этап C).

last_return_reason (0029, ветка security-hardening) хранил ту же причину, что и
review_comment. Перед удалением переносим его текст туда, где review_comment пуст —
так причины возвратов, сделанных до сведения линий, не теряются. При откате
причина возвращается в last_return_reason из review_comment.
"""

from django.db import migrations, models


def copy_reason_forward(apps, schema_editor):
    Attendee = apps.get_model("eventproject", "Attendee")
    rows = (
        Attendee.objects.filter(review_comment="")
        .exclude(last_return_reason__isnull=True)
        .exclude(last_return_reason="")
    )
    for att in rows.only("pk", "last_return_reason").iterator():
        Attendee.objects.filter(pk=att.pk).update(review_comment=att.last_return_reason)


def copy_reason_backward(apps, schema_editor):
    Attendee = apps.get_model("eventproject", "Attendee")
    Attendee.objects.filter(return_count__gt=0).exclude(review_comment="").update(
        last_return_reason=models.F("review_comment")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("eventproject", "0035_attendee_dateadd_idx"),
    ]

    operations = [
        migrations.RunPython(copy_reason_forward, copy_reason_backward),
        migrations.RemoveField(model_name="attendee", name="last_return_reason"),
    ]
