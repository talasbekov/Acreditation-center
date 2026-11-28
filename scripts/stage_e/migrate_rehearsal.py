"""Этап E (п. 2): репетиция миграций на PostgreSQL — 0024 → последняя → 0024 → последняя с данными.

Запуск из Acreditation-center-main с DJANGO_SETTINGS_MODULE, указывающим на отдельную базу PostgreSQL (см. README.md).
Данные — синтетические, создаются историческими моделями схемы 0024.
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import django  # noqa: E402

django.setup()
from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402
from django.db.migrations.executor import MigrationExecutor  # noqa: E402
from django.utils import timezone  # noqa: E402

OLD = "0024_recompute_is_resident"
log = []


def step(name, **data):
    log.append({"step": name, **data})
    print(name, json.dumps(data, ensure_ascii=False, default=str))


def state_apps(target):
    executor = MigrationExecutor(connection)
    return executor.loader.project_state(("eventproject", target)).apps


def leaf():
    executor = MigrationExecutor(connection)
    return [n for app, n in executor.loader.graph.leaf_nodes() if app == "eventproject"][0]


def snapshot():
    with connection.cursor() as c:
        c.execute("select count(*) from eventproject_event")
        events = c.fetchone()[0]
        c.execute("select count(*) from eventproject_request")
        requests = c.fetchone()[0]
        c.execute("select count(*), count(distinct surname), sum(case when photo <> '' then 1 else 0 end) from eventproject_attendee")
        attendees, names, photos = c.fetchone()
    return {"events": events, "requests": requests, "attendees": attendees, "names": names, "photos": photos}


TARGET = leaf()
call_command("migrate", "eventproject", OLD, verbosity=0)
step("migrated_to_old", target=OLD)

apps = state_apps(OLD)
User = apps.get_model("auth", "User")
Event = apps.get_model("eventproject", "Event")
Operator = apps.get_model("eventproject", "Operator")
Request = apps.get_model("eventproject", "Request")
Attendee = apps.get_model("eventproject", "Attendee")
today = date.today()
user = User.objects.create(username="rehearsal_op", password="!")
op = Operator.objects.create(user=user, patronymic="P", phone_number="+7")
events = []
for i in range(2):
    e = Event.objects.create(name_rus=f"Репетиция {i}", name_kaz=f"Репетиция {i}", name_eng=f"Rehearsal {i}",
                             event_code=f"R{i}", date_start=today, date_end=today + timedelta(days=10), city_code="1")
    op.events.add(e)
    events.append(e)
n = 0
for e in events:
    for r in range(3):
        req = Request.objects.create(name=f"R{e.pk}-{r}", event=e, status="Active", created_by=op,
                                     registration_time=timezone.now())
        for a in range(5):
            n += 1
            resident = a % 2 == 0
            Attendee.objects.create(
                surname=f"Репетиционный{n}", firstname="Тест", patronymic="", post="Инженер",
                countryId="1000000105" if resident else "1000000840", docTypeId="1000000001" if resident else "1000000002",
                docSeries="", docNumber=f"N{n}", docIssue="", sexId="1", visitObjects="Зал",
                transcription=f"REPETITION {n}", request=req, dateAdd=timezone.now(), photo=f"event_{e.pk}/p{n}.jpg",
                birthDate=date(1990, 1, 1), docBegin=date(2020, 1, 1), docEnd=date(2034, 1, 1),
                iin=None,
            )
before = snapshot()
step("data_at_old", **before)

call_command("migrate", "eventproject", TARGET, verbosity=0)
after_up = snapshot()
with connection.cursor() as c:
    c.execute("select count(*) from eventproject_attendee where status = 'draft' and coalesce(review_comment, '') = ''")
    drafts = c.fetchone()[0]
    c.execute("select count(*) from eventproject_event where title is not null and start_date is not null")
    backfilled = c.fetchone()[0]
    c.execute("select indexname from pg_indexes where tablename = 'eventproject_attendee' and indexname = 'attendee_dateadd_idx'")
    index = c.fetchone()
step("migrated_up", target=TARGET, drafts_with_empty_comment=drafts, events_backfilled=backfilled,
     dateadd_index=bool(index), **after_up)
assert after_up == before, (before, after_up)
assert drafts == before["attendees"], drafts
assert backfilled == before["events"], backfilled
assert index

call_command("migrate", "eventproject", OLD, verbosity=0)
after_down = snapshot()
step("migrated_down", target=OLD, **after_down)
assert after_down == before, (before, after_down)

call_command("migrate", "eventproject", TARGET, verbosity=0)
again = snapshot()
step("migrated_up_again", target=TARGET, **again)
assert again == before, (before, again)

out = os.environ.get("REHEARSAL_OUT")
if out:
    Path(out).write_text(json.dumps(log, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("REHEARSAL OK")
