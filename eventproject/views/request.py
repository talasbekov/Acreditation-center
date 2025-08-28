import datetime
import json

from datetime import datetime

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required

from directories.models import Sex, Country, DocumentType, Category
from eventproject.models import Event, Operator, Request, Attendee


@login_required(login_url="/user_login/")
def create_request(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        context_dict["event"] = event
        operator = Operator.objects.get(user=request.user)
        req = Request()
        now = datetime.now()
        req.name = now.strftime("%d%m%Y%H%M%S")
        req.event = event
        req.status = "Active"
        req.date_created = now
        req.created_by = operator
        req.registration_time = now
        req.save()
        context_dict["req"] = req
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "request.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def show_request_to_admin(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict["req"] = req
        attendees = Attendee.objects.filter(request=req)
        context_dict["attendees"] = attendees
        countries = Country.objects.all()
        context_dict["countries"] = countries
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
        if req.status == "Sent":
            context_dict["delete_message"] = "Отправлено " + str(req.registration_time)
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "request_admin.html", context_dict)


@login_required(login_url="/user_login/")
def show_request(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict["req"] = req
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        attendees = Attendee.objects.filter(request=req)
        context_dict["attendees"] = attendees
        countries = Country.objects.all()
        context_dict["countries"] = countries
        categories = Category.objects.all()
        context_dict["categories"] = categories
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
        if req.status == "Sent":
            context_dict["success_message"] = "Отправлено " + str(req.registration_time)
        elif req.status == "Checking":
            context_dict["success_message"] = "Заявка готова к отправлению"
            context_dict[
                "delete_message"
            ] = "Внимание!!! Отправка заявки не гарантирует допуск участника в зону проведения охранного мероприятия в установленную дату"
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "request.html", context_dict)


@login_required(login_url="/user_login/")
def delete_request(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.delete()
    except Event.DoesNotExist:
        return HttpResponse("Could not find request")
    return HttpResponseRedirect("/application/")


@login_required(login_url="/user_login/")
def create_request2(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        context_dict["event"] = event
        operator = Operator.objects.get(user=request.user)
        request_set = Request.objects.filter(event=event, status="Sent")
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
        countries = Country.objects.all()
        context_dict["countries"] = countries
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
        list_of_requests = []
        for req in request_set:
            request_dict = model_to_dict(req)
            attendees = Attendee.objects.filter(request=req)
            list_of_attendees = []
            for attendee in attendees:
                attendee_dict = model_to_dict(attendee)
                list_of_attendees.append(attendee_dict)
            request_dict["attendees"] = list_of_attendees
            serialized_request = json.dumps(
                request_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False
            )
            file = open(request_dict["name"] + ".txt", "w")
            file.write(serialized_request)
            file.close()
            list_of_requests.append(request_dict)
        # print("ai  m here")
        event_dict = model_to_dict(event)
        event_dict["requests"] = list_of_requests
        serialized_event = json.dumps(
            event_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False
        )
        print(serialized_event)
        file = open("event_json.txt", "w")
        file.write(serialized_event)
        file.close()

    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "gov3.html", context_dict)
