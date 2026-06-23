from django.db import migrations


def normalize_blank_iin(apps, schema_editor):
    """Story 4.2 (review): legacy-резиденты с ИИН="" → NULL.

    После миграции шифрования (Story 1.2) plaintext "" превратился в
    encrypted "" (не NULL), поэтому такие записи не ловятся `iin__isnull=True`
    и проскальзывают мимо флага дашборда. EncryptedCharField нельзя фильтровать
    по значению, поэтому ищем "" перебором непустых (IS NOT NULL) строк и
    обнуляем их одним UPDATE.
    """
    Attendee = apps.get_model("eventproject", "Attendee")
    blank_ids = [
        a.id
        for a in Attendee.objects.filter(iin__isnull=False).only("id", "iin").iterator()
        if a.iin == ""
    ]
    if blank_ids:
        Attendee.objects.filter(id__in=blank_ids).update(iin=None)


class Migration(migrations.Migration):

    dependencies = [
        ("eventproject", "0020_attendee_status"),
    ]

    operations = [
        migrations.RunPython(normalize_blank_iin, migrations.RunPython.noop),
    ]
