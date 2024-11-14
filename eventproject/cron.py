import shutil
from django.utils import timezone
from datetime import timedelta
from eventproject.models import Event

"""
def my_cron_job():
    try:
        enddate = date.today()
        startdate = enddate - timedelta(days=900)
        event_list = Event.objects.filter(date_end__range=[startdate, enddate])
        count = len(event_list)
        print(count)
        for event in event_list:
            print(event.id)
            mydir = "media/event_"+str(event.id)
            print(mydir)
            try:
                shutil.rmtree(mydir)
                print("perfect")
            except OSError as e:
                print("Error: %s - %s." % (e.filename, e.strerror))
            event.delete()
        try:
            shutil.rmtree("output")
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))
    except Exception as e:
        return HttpResponse("Some error occured")
    # your functionality goes here
    """


def my_cron_job():
    try:
        # Измените количество минут здесь
        minutes = 3
        enddate = timezone.now()
        startdate = enddate - timedelta(minutes=minutes)
        event_list = Event.objects.filter(date_end__range=[startdate, enddate])
        count = len(event_list)
        print(count)
        for event in event_list:
            print(event.id)
            mydir = "media/event_" + str(event.id)
            print(mydir)
            try:
                shutil.rmtree(mydir)
                print("perfect")
            except OSError as e:
                print("Error: %s - %s." % (e.filename, e.strerror))
            event.delete()
        try:
            shutil.rmtree("output")
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))
    except Exception:
        return HttpResponse("Some error occurred")
