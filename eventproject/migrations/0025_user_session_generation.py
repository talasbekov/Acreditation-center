from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("eventproject", "0024_recompute_is_resident"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserSessionGeneration",
            fields=[
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True, related_name="session_generation", serialize=False,
                    to=settings.AUTH_USER_MODEL)),
                ("generation", models.PositiveBigIntegerField(default=1)),
            ],
        ),
        migrations.RunSQL(
            # An old session without a marker is valid only for accounts with no known revocation.
            """INSERT INTO eventproject_usersessiongeneration (user_id, generation)
               SELECT DISTINCT op.user_id, 1
               FROM eventproject_operatoraccessevent AS history
               JOIN eventproject_operator AS op ON op.id = history.operator_id
               WHERE history.event_type = 'deactivated'
               UNION
               SELECT id, 1 FROM auth_user WHERE NOT is_active""",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
