import asyncio
import shutil
from datetime import date, timedelta

from django.test import RequestFactory

from eventproject.models import Event
from eventproject.views.integration.integrate import kazexpo_receive


# def my_cron_job():
#     try:
#         enddate = date.today()
#         startdate = enddate - timedelta(days=900)
#         event_list = Event.objects.filter(date_end__range=[startdate, enddate])
#         count = len(event_list)
#         print(count)
#         for event in event_list:
#             print(event.id)
#             mydir = "media/event_" + str(event.id)
#             print(mydir)
#             try:
#                 shutil.rmtree(mydir)
#                 print("perfect")
#             except OSError as e:
#                 print("Error: %s - %s." % (e.filename, e.strerror))
#             event.delete()
#         try:
#             shutil.rmtree("output")
#         except OSError as e:
#             print("Error: %s - %s." % (e.filename, e.strerror))
#     except Exception as e:
#         return HttpResponse("Some error occured")
#     # your functionality goes here

def kazexpo_import_job():
    """
    Этот код будет запускаться из crontab каждые N минут/часов.
    """
    # создаём простой GET-запрос
    try:
        result = asyncio.run(kazexpo_receive(event_id=2, operator_id=1))
        # По желанию: логируем куда-нибудь
        print("KazExpo import job result:", result)
    except Exception as e:
        print("KazExpo import job failed:", e)