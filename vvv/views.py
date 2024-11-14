import datetime
import secrets

from datetime import date, timedelta

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test

from directories.models import Sex, Country, DocumentType, City
from eventproject.models import Event, Operator, Request, Attendee


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def index(request):
    # Construct a dictionary to pass to the template engine as its context.
    # Note the key boldmessage is the same as {{ boldmessage }} in the template!
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    event_list = Event.objects.filter(date_end__range=[startdate, enddate]).order_by(
        "date_start"
    )
    operators = Operator.objects.all()
    cities = City.objects.all()
    context_dict = {"events": event_list}
    context_dict["operators"] = operators
    context_dict["cities"] = cities
    return render(request, "index.html", context=context_dict)


def show_admin(request, success_message):
    # Construct a dictionary to pass to the template engine as its context.
    # Note the key boldmessage is the same as {{ boldmessage }} in the template!
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    event_list = Event.objects.filter(date_end__range=[startdate, enddate]).order_by(
        "date_start"
    )
    operators = Operator.objects.all()
    cities = City.objects.all()
    context_dict = {"events": event_list}
    context_dict["operators"] = operators
    context_dict["success_message"] = success_message
    context_dict["cities"] = cities
    return render(request, "index.html", context=context_dict)


def show_admin_error(request, error_message):
    # Construct a dictionary to pass to the template engine as its context.
    # Note the key boldmessage is the same as {{ boldmessage }} in the template!
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    event_list = Event.objects.filter(date_end__range=[startdate, enddate]).order_by(
        "date_start"
    )
    operators = Operator.objects.all()
    cities = City.objects.all()
    context_dict = {"events": event_list}
    context_dict["operators"] = operators
    context_dict["error_message"] = error_message
    context_dict["cities"] = cities
    return render(request, "index.html", context=context_dict)


@login_required(login_url="/user_login/")
def application(request):
    if not request.user.is_authenticated:
        return HttpResponse("You are logged in.")
    user = request.user
    if user.is_superuser:
        return HttpResponseRedirect("/avmac/")
    operator = Operator.objects.get(user=user)
    cities = City.objects.all()
    if not operator:
        return HttpResponse("You are logged in.")
    startdate = date.today()
    enddate = startdate + timedelta(days=600)
    events = operator.events.filter(date_end__range=[startdate, enddate])
    reqs = Request.objects.filter(created_by=operator).order_by("-date_created")
    return render(
        request,
        "gov2.html",
        {
            "user": user,
            "operator": operator,
            "events": events,
            "reqs": reqs,
            "cities": cities,
        },
    )


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def new_password(request, username):
    context_dict = {}
    try:
        user = User.objects.get(username=username)
        operator = Operator.objects.get(user=user)
        password = secrets.token_urlsafe(8)
        user.set_password(password)
        user.save()
        startdate = date.today()
        enddate = startdate + timedelta(days=900)
        event_list = operator.events.filter(
            date_end__range=[startdate, enddate]
        ).order_by("-date_start")
        reqs = Request.objects.filter(created_by=operator).order_by("-date_created")
        context_dict["events"] = event_list
        context_dict["operator"] = operator
        context_dict["requests"] = reqs
        context_dict["success_message"] = "Сгенерирован новый пароль: " + password
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "operator.html", context_dict)


@login_required(login_url="/user_login/")
def preview(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict["req"] = req
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.status = "Checking"
        req.save()
        attendees = Attendee.objects.filter(request=req)
        context_dict["attendees"] = attendees
        countries = Country.objects.all()
        context_dict["countries"] = countries
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
        context_dict["success_message"] = "Заявка готова к отправлению"
        context_dict["delete_message"] = (
            "Внимание!!! Отправка заявки не гарантирует допуск участника в зону проведения охранного мероприятия в установленную дату"
        )
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "request.html", context_dict)


@login_required(login_url="/user_login/")
def back_to_change(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict["req"] = req
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.status = "Active"
        req.save()
        attendees = Attendee.objects.filter(request=req)
        context_dict["attendees"] = attendees
        countries = Country.objects.all()
        context_dict["countries"] = countries
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "request.html", context_dict)


@login_required(login_url="/user_login/")
def send(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict["req"] = req
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.status = "Sent"
        req.registration_time = datetime.now()
        req.save()
        attendees = Attendee.objects.filter(request=req)
        context_dict["attendees"] = attendees
        countries = Country.objects.all()
        context_dict["countries"] = countries
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
        context_dict["success_message"] = "Отправлено " + str(req.registration_time)
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "request.html", context_dict)


@login_required(login_url="/user_login/")
def user_logout(request):
    logout(request)
    return HttpResponseRedirect("/user_login/")


@login_required(login_url="/user_login/")
def change_password(request):
    context_dict = {}
    try:
        if request.method == "POST":
            old_password = request.POST["old_password"]
            new_password = request.POST["new_password"]
            new_password_repeat = request.POST["new_password_repeat"]
            if new_password != new_password_repeat:
                context_dict["error_message"] = "Введите новый пароль два раза"
                return render(request, "change_password_result.html", context_dict)
            if request.user.check_password(old_password):
                request.user.set_password(new_password)
                request.user.save()
                context_dict["success_message"] = "Пароль успешно изменен"
                return render(request, "change_password_result.html", context_dict)
            else:
                context_dict["error_message"] = "Не удалось подтвердить данные"
                return render(request, "change_password_result.html", context_dict)
    except Exception:
        print("unknown")
    return render(request, "change_password.html", context_dict)


def user_login(request):
    context = RequestContext(request)
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                if user.is_superuser:
                    return HttpResponseRedirect("/avmac/")
                else:
                    return HttpResponseRedirect("/application/")
            else:
                return HttpResponse("Your account is suspended")
        else:
            return render(
                request,
                "gov.html",
                context={"error_message": "Неправильный логин или пароль"},
            )
    return render(request, "gov.html", context={})


# return render_to_response('gov.html', , context)
