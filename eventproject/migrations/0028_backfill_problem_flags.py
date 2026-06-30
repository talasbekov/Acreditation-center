"""Story fe-3.1 — backfill problem_flags для строк, уже находящихся в очереди.

Флаги популируются при draft→submitted (compute_problem_flags). Строки, бывшие
submitted/in_review ДО деплоя fe-3.1, остались бы с `[]` навсегда → невидимы для
`?problem=` (фильтр недо-репортит существующие проблемы). Здесь backfill'им
вычислимый-в-SQL флаг `no_photo` (photo="" → нет фото; без декрипта ИИН). Остальные
члены набора не имеют SQL-вычислимого сигнала пост-фактум (см. problem_flags.py).
"""

from django.db import migrations


def backfill_no_photo(apps, schema_editor):
    Attendee = apps.get_model("eventproject", "Attendee")
    # Только строки очереди без фото. На момент миграции (один деплой, до обслуживания)
    # все строки имеют problem_flags=[] → перезапись безопасна и идемпотентна.
    Attendee.objects.filter(
        status__in=["submitted", "in_review"], photo=""
    ).update(problem_flags=["no_photo"])


class Migration(migrations.Migration):

    dependencies = [
        ("eventproject", "0027_attendee_problem_flags"),
    ]

    operations = [
        # reverse = noop: откат backfill'а не разрушает данные (флаги — производные).
        migrations.RunPython(backfill_no_photo, migrations.RunPython.noop),
    ]
