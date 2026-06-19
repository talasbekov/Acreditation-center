"""
ROLLBACK PLAN:
  python manage.py migrate eventproject 0008
  Это запустит backwards() и вернёт данные ИИН во временное plaintext-поле.

WARNING: Потеря FERNET_KEYS делает чтение и rollback невозможными.
         Сохраните ключ в надёжном месте ДО запуска migration.

DO NOT USE: migrate --fake
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import migrations

from eventproject.fernet_fields import EncryptedCharField


BATCH_SIZE = 100
IIN_ENCRYPTION_HELP_TEXT = (
    "ИИН зашифрован at rest через django-fernet-fields. "
    "Прямой фильтр Attendee.objects.filter(iin=...) невозможен. "
    "Используйте validators/iin.py для валидации перед сохранением."
)


def _ensure_fernet_keys():
    if not getattr(settings, "FERNET_KEYS", None):
        raise ImproperlyConfigured("FERNET_KEYS must be configured before migrating IIN data.")


def _iter_batches(queryset):
    """Yields batches of PKs using pk__gt cursor — stable under concurrent inserts/deletes."""
    last_pk = 0
    while True:
        batch = list(
            queryset.filter(pk__gt=last_pk).values_list("pk", flat=True)[:BATCH_SIZE]
        )
        if not batch:
            break
        yield batch
        last_pk = batch[-1]


def encrypt_existing_iin(apps, schema_editor):
    # Note: atomic=True on this migration wraps the entire operation in one transaction.
    # Any exception triggers a full rollback — per-record savepoints are not needed.
    _ensure_fernet_keys()
    Attendee = apps.get_model("eventproject", "Attendee")
    queryset = Attendee.objects.filter(iin__isnull=False).order_by("pk")

    for batch in _iter_batches(queryset):
        for attendee in Attendee.objects.filter(pk__in=batch).order_by("pk"):
            original_iin = attendee.iin
            if original_iin in ("", None):
                continue
            attendee.iin_encrypted = original_iin
            attendee.save(update_fields=["iin_encrypted"])
            # Verify ORM round-trip decryption succeeds before moving on.
            refreshed = Attendee.objects.get(pk=attendee.pk)
            if refreshed.iin_encrypted != original_iin:
                raise ValueError(f"Encryption verification failed for attendee {attendee.pk}")


def decrypt_existing_iin(apps, schema_editor):
    # Note: atomic=True wraps the full backward migration in one transaction.
    _ensure_fernet_keys()
    Attendee = apps.get_model("eventproject", "Attendee")
    queryset = Attendee.objects.filter(iin_encrypted__isnull=False).order_by("pk")

    for batch in _iter_batches(queryset):
        for attendee in Attendee.objects.filter(pk__in=batch).order_by("pk"):
            original_iin = attendee.iin_encrypted
            if original_iin in ("", None):
                continue
            attendee.iin = original_iin
            attendee.save(update_fields=["iin"])
            refreshed = Attendee.objects.get(pk=attendee.pk)
            if refreshed.iin != original_iin:
                raise ValueError(f"Decryption verification failed for attendee {attendee.pk}")


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("eventproject", "0008_alter_attendee_docissue_alter_attendee_docnumber_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendee",
            name="iin_encrypted",
            field=EncryptedCharField(
                blank=True,
                help_text=IIN_ENCRYPTION_HELP_TEXT,
                max_length=12,
                null=True,
            ),
        ),
        migrations.RunPython(encrypt_existing_iin, decrypt_existing_iin),
    ]
