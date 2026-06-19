from django.db import migrations

# ROLLBACK NOTE:
# Rolling back 0010 alone (migrate eventproject 0009) is safe:
#   - RenameField reverse restores iin_encrypted column with encrypted data
#   - RemoveField reverse AddField creates empty iin column
# Then rolling back 0009 runs decrypt_existing_iin which restores plaintext from iin_encrypted.
#
# IMPORTANT: Always roll back 0010 AND 0009 together via: migrate eventproject 0008
# Rolling back only 0010 leaves iin empty — run 0009 backward immediately after.


class Migration(migrations.Migration):
    dependencies = [
        ("eventproject", "0009_attendee_iin_encrypted"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="attendee",
            name="iin",
        ),
        migrations.RenameField(
            model_name="attendee",
            old_name="iin_encrypted",
            new_name="iin",
        ),
    ]
