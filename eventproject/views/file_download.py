import os
import json
import shutil
import mimetypes

from django.http import HttpResponse, FileResponse, StreamingHttpResponse
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.contrib.auth.decorators import user_passes_test

from wsgiref.util import FileWrapper

from eventproject.models import Event, Request, Attendee


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def download_json(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        request_set = Request.objects.filter(event=event, status='Sent')
        list_of_attendees = []
        for req in request_set:
            request_dict = model_to_dict(req)
            attendees = Attendee.objects.filter(request=req)
            for attendee in attendees:
                attendee_dict = model_to_dict(attendee)
                list_of_attendees.append(attendee_dict)
            req.status = "Exported"
            req.save()
        event_dict = model_to_dict(event)
        event_dict['attendees'] = list_of_attendees
        serialized_event = json.dumps(event_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False)
        return HttpResponse(serialized_event, content_type="application/json")
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'event.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def download_guests_json(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        request_set = Request.objects.filter(event=event, status="Sent")
        list_of_attendees = []
        for req in request_set:
            request_dict = model_to_dict(req)
            attendees = Attendee.objects.filter(request=req)
            for attendee in attendees:
                attendee_dict = model_to_dict(attendee)
                list_of_attendees.append(attendee_dict)
            req.status = "Exported"
            req.save()
        event_dict = model_to_dict(event)
        event_dict["attendees"] = list_of_attendees
        serialized_event = json.dumps(
            event_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False
        )
        return HttpResponse(serialized_event, content_type="application/json")
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "event.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def download_all_guests_json(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        request_set = Request.objects.filter(
            event=event, status__in=["Sent", "Exported"]
        )
        list_of_attendees = []
        for req in request_set:
            request_dict = model_to_dict(req)
            attendees = Attendee.objects.filter(request=req)
            for attendee in attendees:
                attendee_dict = model_to_dict(attendee)
                list_of_attendees.append(attendee_dict)
            req.status = "Exported"
            req.save()
        event_dict = model_to_dict(event)
        event_dict["attendees"] = list_of_attendees
        serialized_event = json.dumps(
            event_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False
        )
        return HttpResponse(serialized_event, content_type="application/json")
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "event.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def download_request_json(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(id=request_id)
        request_dict = model_to_dict(req)
        attendees = Attendee.objects.filter(request=req)
        list_of_attendees = []
        for attendee in attendees:
            attendee_dict = model_to_dict(attendee)
            list_of_attendees.append(attendee_dict)
        request_dict["attendees"] = list_of_attendees
        request_dict["event"] = req.event
        serialized_event = json.dumps(
            request_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False
        )
        req.status = "Exported"
        req.save()
        return HttpResponse(serialized_event, content_type="application/json")
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "event.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def download_photos(request, event_id):
    context_dict = {}
    try:
        if os.path.exists("event_" + str(event_id) + ".zip"):
            os.remove("event_" + str(event_id) + ".zip")
            print("The file has been deleted successfully")
        else:
            print("The file does not exist!")
        dir_name = "media/event_" + str(event_id)
        if not os.path.isdir(dir_name):
            return HttpResponse("No photos uploaded yet")

        zip_address = "media/event_" + str(event_id)
        file = open(zip_address + "/test.txt", "w")
        file.close()

        # Архивируем директорию, указывая корень архива как родительскую директорию
        shutil.make_archive(f"media/event_{event_id}", "zip", "media", f"event_{event_id}")

        # Открываем и отправляем созданный архив
        zip = open(dir_name + ".zip", "rb")
        response = FileResponse(zip)
        return response

    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "event.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def download_file(request, event_id):
    context_dict = {}
    try:
        the_file = "event_" + str(event_id) + ".zip"
        filename = os.path.basename(the_file)
        chunk_size = 8192
        response = StreamingHttpResponse(
            FileWrapper(open(the_file, "rb"), chunk_size),
            content_type=mimetypes.guess_type(the_file)[0],
        )
        response["Content-Length"] = os.path.getsize(the_file)
        response["Content-Disposition"] = "attachment; filename=%s" % filename
        return response
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "event.html", context_dict)


# @user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
# def prepare_file(request, event_id):
#     context_dict = {}
#     try:
#         p = Process(target=download_photos_async, args=(event_id,))
#         p.start()
#         context_dict[
#             "success_message"
#         ] = "Архивируется файлы, через какое-то время обновите страницу"
#     except Request.DoesNotExist:
#         return HttpResponse("Could not find event")
#     return render(request, "event.html", context_dict)
