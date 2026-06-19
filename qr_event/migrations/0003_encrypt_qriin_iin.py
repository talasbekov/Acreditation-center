from django.db import migrations

import eventproject.fernet_fields
import qr_event.models

# ROLLBACK NOTE (как у eventproject 0009/0010):
# Обратная миграция восстанавливает plaintext-колонку iin из iin_encrypted.
# Все операции в одном файле, откат: migrate qr_event 0002.


def encrypt_existing_iin(apps, schema_editor):
    QrIin = apps.get_model("qr_event", "QrIin")
    for obj in QrIin.objects.all().iterator():
        obj.iin_encrypted = obj.iin
        obj.save(update_fields=["iin_encrypted"])


def decrypt_existing_iin(apps, schema_editor):
    QrIin = apps.get_model("qr_event", "QrIin")
    for obj in QrIin.objects.all().iterator():
        obj.iin = obj.iin_encrypted
        obj.save(update_fields=["iin"])


class Migration(migrations.Migration):
    dependencies = [
        ("qr_event", "0002_qriin_qr_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="qriin",
            name="iin_encrypted",
            field=eventproject.fernet_fields.EncryptedCharField(
                max_length=12, null=True, blank=True
            ),
        ),
        migrations.RunPython(encrypt_existing_iin, decrypt_existing_iin),
        migrations.RemoveField(
            model_name="qriin",
            name="iin",
        ),
        migrations.RenameField(
            model_name="qriin",
            old_name="iin_encrypted",
            new_name="iin",
        ),
        migrations.AlterField(
            model_name="qriin",
            name="iin",
            field=eventproject.fernet_fields.EncryptedCharField(
                max_length=12,
                validators=[
                    qr_event.models.iin_validator,
                    qr_event.models.iin_kz_validator,
                ],
            ),
        ),
    ]
