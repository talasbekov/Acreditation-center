import secrets

from datetime import date, timedelta

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test

from .views import show_admin, show_admin_error
from eventproject.models import Event, Operator, Request


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def add_operator(request):
    try:
        if request.method == "POST":
            first_name = request.POST["first_name"]
            last_name = request.POST["last_name"]
            patronymic = request.POST["patronymic"]
            login = request.POST["login"]
            phone_number = request.POST["phone_number"]
            password = secrets.token_urlsafe(8)
            event_code = request.POST["event_code"]
            workplace = request.POST["workplace"]

            user = User(
                username=login,
                first_name=first_name,
                last_name=last_name,
                password=password,
            )
            user.save()
            user.set_password(password)
            user.save()
            event = Event.objects.get(pk=event_code)
            operator = Operator(
                user=user,
                phone_number=phone_number,
                patronymic=patronymic,
                workplace=workplace,
            )
            operator.save()
            operator.events.add(event)
            operator.save()
            success_message = (
                "Пользователь " + login + " успешно создан! Пароль: " + password
            )
            return show_admin(request, success_message)
    except Exception as e:
        error_message = "Не удалось создать пользователя. Возможно повторояется логин с другим пользователем"
        return show_admin_error(request, error_message)

    return HttpResponseRedirect("/avmac/")


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def bind_operators(request):
    # try:
    if request.method == "POST":
        operators = request.POST.getlist("operator")
        event_code = request.POST["event_code"]

        event = Event.objects.get(id=event_code)
        for o in operators:
            operator = Operator.objects.get(id=o)
            operator.events.add(event)
            operator.save()
        success_message = "Операторы успешно добавлены"
        return HttpResponseRedirect("/show_event/%s/" % event.id)
        # return HttpResponseRedirect('/show_event/', event.id)
    # except Exception as e:
    #     error_message = "Произошла ошибка"
    #     return show_admin_error(request, error_message)

    return HttpResponseRedirect("/avmac/")


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def show_operator(request, operator_id):
    context_dict = {}
    try:
        operator = Operator.objects.get(pk=operator_id)
        startdate = date.today()
        enddate = startdate + timedelta(days=900)
        event_list = operator.events.filter(
            date_end__range=[startdate, enddate]
        ).order_by("-date_start")
        reqs = Request.objects.filter(created_by=operator).order_by("-date_created")
        context_dict["events"] = event_list
        context_dict["operator"] = operator
        context_dict["reqs"] = reqs
    except Exception as e:
        return HttpResponse("Could not find operator")
    return render(request, "operator.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def delete_operator(request, username):
    context_dict = {}
    try:
        user = User.objects.get(username=username)
        operator = Operator.objects.get(user=user)
        success_message = user.first_name + " " + user.last_name + " успешно удален"
        operator.delete()
        user.delete()
        return show_admin(request, success_message)
    except Exception as e:
        return HttpResponse("Could not find operator")
    return render(request, "operator.html", context_dict)
