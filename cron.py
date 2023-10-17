import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventproject.settings")

import django

django.setup()

import os
import shutil
from datetime import date, timedelta, datetime
from eventproject.models import Event, Operator, Request, Attendee


def my_cron_job():
    try:
        enddate = date.today()
        startdate = enddate - timedelta(days=900)
        event_list = Event.objects.filter(date_end__range=[startdate, enddate])
        count = len(event_list)
        print(count)
        for event in event_list:
            print(event.id)
            mydir = "event/Scripts/eventproject/media/event_" + str(event.id)
            print(mydir)
            directory = os.getcwd()
            try:
                shutil.rmtree(mydir)
                print("perfect")
            except OSError as e:
                print("pity")
            event.delete()
        try:
            shutil.rmtree("event/Scripts/eventproject/output")
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))
    except Exception as e:
        return HttpResponse("Some error occured")
    # your functionality goes here
