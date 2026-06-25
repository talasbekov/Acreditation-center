# BE-12: пересчёт is_resident существующих строк из countryId.
# Миграция 0019 проставила is_resident=default=True всем строкам и не пересчитывала
# по фактическому countryId → исторические нерезиденты помечены резидентами до
# пересохранения. Один раз приводим в соответствие со справочной логикой residency.

from django.conf import settings
from django.db import migrations


def _kz_country_id():
    return str(getattr(settings, "KZ_COUNTRY_ID", "1000000105")).strip()


def recompute_is_resident(apps, schema_editor):
    Attendee = apps.get_model("eventproject", "Attendee")
    kz = _kz_country_id()
    for a in Attendee.objects.all().only("id", "countryId", "is_resident").iterator():
        correct = a.countryId is not None and str(a.countryId).strip() == kz
        if a.is_resident != correct:
            a.is_resident = correct
            a.save(update_fields=["is_resident"])


def noop(apps, schema_editor):
    # Необратимо по смыслу (исходное состояние было некорректным) — no-op откат.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('eventproject', '0023_attendee_attendee_status_valid_and_more'),
    ]

    operations = [
        migrations.RunPython(recompute_is_resident, noop),
    ]
