from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from eventproject.operator_activation import send_operator_link
import logging

from datetime import date, timedelta

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from .views import show_admin, show_admin_error
from eventproject.models import Event, Operator, Request

logger = logging.getLogger("eventproject")


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_POST
@csrf_protect
def add_operator(request):
    try:
        email = request.POST.get("email", "").strip()
        validate_email(email)
        with transaction.atomic():
            event = Event.objects.get(pk=request.POST["event_code"])
            user = User.objects.create_user(
                username=request.POST["login"], email=email, password=None,
                first_name=request.POST["first_name"], last_name=request.POST["last_name"],
            )
            operator = Operator.objects.create(
                user=user, phone_number=request.POST["phone_number"],
                patronymic=request.POST["patronymic"], workplace=request.POST["workplace"],
            )
            operator.events.add(event)
    except (KeyError, ValueError, ValidationError, IntegrityError, Event.DoesNotExist):
        return show_admin_error(request, "Проверьте данные оператора, email и уникальность логина.")

    if not send_operator_link(operator):
        return show_admin_error(request, "Оператор создан. Письмо не отправлено. Проверьте настройки почты и повторите отправку из карточки оператора.")
    return show_admin(request, "Оператор создан. Ссылка для установки пароля отправлена на его email.")


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def bind_operators(request):
    # try:
    if request.method == "POST":
        operators = request.POST.getlist("operator")
        # Этап E: неполная или неверная форма раньше давала 500 — теперь сообщение администратору.
        try:
            event = Event.objects.get(id=request.POST.get("event_code", ""))
            selected = [Operator.objects.get(id=o) for o in operators]
        except (ValueError, Event.DoesNotExist, Operator.DoesNotExist):
            return show_admin_error(request, "Не удалось привязать операторов. Проверьте мероприятие и выбранных операторов.")
        for operator in selected:
            operator.events.add(event)
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
        logger.error("show_operator failed")
        return HttpResponse("Could not find operator")
    return render(request, "operator.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_POST
@csrf_protect
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
        logger.error("delete_operator failed")
        return HttpResponse("Could not find operator")
    return render(request, "operator.html", context_dict)
