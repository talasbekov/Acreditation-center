import os
import shutil
import logging
import datetime

from datetime import date, timedelta, datetime

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from .views import show_admin, show_admin_error
from directories.models import City
from eventproject.models import Event, Operator, Request

logger = logging.getLogger("eventproject")


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def create_event(request):
    if request.method == "POST":
        # Этап E: неполная форма из прямого POST раньше давала 500 (KeyError/ValueError).
        name_rus = request.POST.get("name_rus", "")
        name_kaz = request.POST.get("name_kaz", "")
        name_eng = request.POST.get("name_eng", "")
        event_code = request.POST.get("event_code", "")
        city = request.POST.get("city", "")
        today = date.today()
        try:
            sd = datetime.strptime(request.POST.get("date_start", ""), "%Y-%m-%d").date()
            ed = datetime.strptime(request.POST.get("date_end", ""), "%Y-%m-%d").date()
        except ValueError:
            return show_admin_error(request, "Не удалось создать мероприятие. Укажите даты начала и окончания.")
        if name_rus == "":
            error_message = (
                "Не удалось создать мероприятие. Название мероприятия отсутствует"
            )
            return show_admin_error(request, error_message)
        if ed < sd:
            error_message = "Не удалось создать мероприятие. Дата окончания не может быть раньше даты создания"
            return show_admin_error(request, error_message)
        if ed < today:
            error_message = "Не удалось создать мероприятие. Истек дата окончания"
            return show_admin_error(request, error_message)
        event = Event(
            name_kaz=name_kaz,
            name_rus=name_rus,
            name_eng=name_eng,
            event_code=event_code,
            date_start=sd,
            date_end=ed,
            title=name_rus,
            start_date=sd,
            end_date=ed,
            city_code=city,
        )
        event.save()
        success_message = "Мероприятие " + name_rus + " успешно создано"
        return show_admin(request, success_message)

    return HttpResponseRedirect("/avmac/")


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def add_operator_to_event(request):
    try:
        if request.method == "POST":
            operator_id = request.POST["operator_id"]
            event_id = request.POST["event_id"]
            operator = Operator.objects.get(id=operator_id)
            event = Event.objects.get(id=event_id)
            operator.events.add(event)
            operator.save()
            success_message = (
                "Пользователью "
                + operator.user.last_name
                + " "
                + operator.user.first_name
                + " успешно предоставлен доступ на мероприятие "
                + event.name_rus
            )
            return show_admin(request, success_message)
    except Exception as e:
        logger.error("add_operator_to_event failed")
        error_message = "Не удалось добавить пользователя."
        return show_admin_error(request, error_message)

    return HttpResponseRedirect("/avmac/")


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_POST
@csrf_protect
def unbind_event(request, event_id, username):
    context_dict = {}
    try:
        user = User.objects.get(username=username)
        operator = Operator.objects.get(user=user)
        event = Event.objects.get(pk=event_id)
        operator.events.remove(event)
        success_message = (
            event.name_rus
            + " успешно откреплен от пользователя "
            + user.last_name
            + " "
            + user.first_name
        )
        return show_admin(request, success_message)
    except Exception as e:
        logger.error("unbind_event failed")
        return HttpResponse("Could not find operator")
    return render(request, "operator.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def show_event(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        # P2: пользователь оператора и автор заявки загружаются одним JOIN —
        # шаблон выводит их имена для каждой строки.
        operators = list(Operator.objects.filter(events=event).select_related("user"))
        assigned_ids = {o.pk for o in operators}
        reqs = Request.objects.filter(event=event, status__in=["Sent", "Exported"]).select_related("created_by__user")
        active_reqs = Request.objects.filter(
            event=event, status__in=["Active", "Checking"]
        ).select_related("created_by__user")
        cities = City.objects.all()
        context_dict = {"events": [event]}
        context_dict["operators"] = operators
        context_dict["other_operators"] = list(
            Operator.objects.exclude(pk__in=assigned_ids).select_related("user").order_by("user__last_name")
        )
        context_dict["event"] = event
        context_dict["reqs"] = reqs
        context_dict["active_reqs"] = active_reqs
        context_dict["cities"] = cities
        context_dict["unexported"] = reqs.exclude(status="Exported").count()
        zip_name = "event_" + str(event_id) + ".zip"
        if os.path.isfile(zip_name):
            context_dict["file"] = zip_name
            size = os.path.getsize(zip_name)
            context_dict["file_size"] = str(size / 1000000) + " MB"
            ms = os.path.getmtime(zip_name)
            context_dict["file_time"] = datetime.fromtimestamp(ms)
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "event.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_POST
@csrf_protect
def delete_event(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        # Абсолютный путь из MEDIA_ROOT — rmtree не должен зависеть от CWD.
        mydir = os.path.join(settings.MEDIA_ROOT, "event_" + str(event.id))
        try:
            shutil.rmtree(mydir)
        except FileNotFoundError:
            pass
        except OSError:
            logging.getLogger(__name__).error("Event media cleanup failed")
            return HttpResponse("Не удалось удалить файлы мероприятия.", status=503)
        success_message = "Мероприятие: " + event.name_rus + " успешно удалено"
        event.delete()
        return show_admin(request, success_message)
    except Event.DoesNotExist:
        return HttpResponse("Could not find event", status=404)
    return render(request, "event.html", context_dict)

from django.db.models import Count, Prefetch
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from eventproject.permissions import IsSuperoperator
from eventproject.serializers import (
    EventSerializer,
    CategorySerializer,
    get_operator_events
)
from eventproject.audit import audit_log
from eventproject.models import Event, Category

class EventViewSet(ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsSuperoperator]

    def get_queryset(self):
        # Супероператор/Суперпользователь видит все события.
        # Prefetch категорий с аннотацией attendee_count — устраняем N+1 на списке
        # (иначе по одному COUNT-запросу на каждую категорию каждого события).
        return get_operator_events(self.request.user).prefetch_related(
            Prefetch(
                "categories",
                queryset=Category.objects.annotate(_attendee_count=Count("attendees")),
            )
        ).order_by("id")

    def perform_create(self, serializer):
        event = serializer.save(created_by=self.request.user)
        audit_log(
            user=self.request.user,
            action="event.create",
            obj_type="Event",
            obj_id=str(event.id),
            ip=self.request.META.get("REMOTE_ADDR", ""),
        )

    @action(detail=True, methods=["get", "post"],
            permission_classes=[IsSuperoperator])
    def categories(self, request, pk=None):
        event = self.get_object()
        if request.method == "GET":
            categories = event.categories.all()
            serializer = CategorySerializer(categories, many=True)
            return Response(serializer.data)
        elif request.method == "POST":
            serializer = CategorySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            category = serializer.save(event=event)
            audit_log(
                user=request.user,
                action="category.create",
                obj_type="Category",
                obj_id=str(category.id),
                ip=request.META.get("REMOTE_ADDR", ""),
            )
            return Response(CategorySerializer(category).data,
                            status=status.HTTP_201_CREATED)
