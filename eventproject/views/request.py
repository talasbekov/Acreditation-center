from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from directories.models import Sex, Country, DocumentType, Category
from eventproject.audit import audit_log
from eventproject.models import Event, Operator, Request, Attendee


@login_required(login_url="/user_login/")
def create_request(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        context_dict["event"] = event
        operator = Operator.objects.get(user=request.user)
        req = Request()
        now = timezone.now()
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
@require_POST
@csrf_protect
def delete_request(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        user = request.user
        if not user.is_superuser:
            operator = Operator.objects.get(user=user)
            if req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")
        # hd-4.2 (AC-4): obj_id — ДО .delete() (Django обнуляет pk после удаления).
        req_pk = str(req.id)
        req.delete()
        audit_log(
            user=user,
            action="request.delete",
            obj_type="Request",
            obj_id=req_pk,
            ip=request.META.get("REMOTE_ADDR", ""),
        )
    except Request.DoesNotExist:
        return HttpResponse("Could not find request", status=404)
    return HttpResponseRedirect("/application/")


@login_required(login_url="/user_login/")
def create_request2(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        context_dict["event"] = event
        operator = Operator.objects.get(user=request.user)
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
        countries = Country.objects.all()
        context_dict["countries"] = countries
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "gov3.html", context_dict)
