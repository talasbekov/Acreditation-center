from django.db import migrations
from django.db.models import F, Q
from django.db.models.functions import Trim


def fill_legacy_event_fields(apps, schema_editor):
    events = apps.get_model("eventproject", "Event").objects.using(schema_editor.connection.alias)
    titles = events.alias(current_title=Trim("title"), russian_title=Trim("name_rus"))
    titles.filter(Q(title__isnull=True) | Q(current_title="")).exclude(
        name_rus__isnull=True,
    ).exclude(russian_title="").update(title=F("name_rus"))
    events.filter(start_date__isnull=True, date_start__isnull=False).update(start_date=F("date_start"))
    events.filter(end_date__isnull=True, date_end__isnull=False).update(end_date=F("date_end"))


class Migration(migrations.Migration):
    dependencies = [("eventproject", "0025_user_session_generation")]
    operations = [migrations.RunPython(fill_legacy_event_fields, migrations.RunPython.noop)]
