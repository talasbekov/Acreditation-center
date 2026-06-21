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
        name_rus = request.POST["name_rus"]
        name_kaz = request.POST["name_kaz"]
        name_eng = request.POST["name_eng"]
        event_code = request.POST["event_code"]
        date_start = request.POST["date_start"]
        date_end = request.POST["date_end"]
        city = request.POST["city"]
        today = date.today()
        sd = datetime.strptime(date_start, "%Y-%m-%d").date()
        ed = datetime.strptime(date_end, "%Y-%m-%d").date()
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
            date_start=date_start,
            date_end=date_end,
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
        logger.exception("add_operator_to_event failed: %s", e)
        error_message = "Не удалось добавить пользователя."
        return show_admin_error(request, error_message)

    return HttpResponseRedirect("/avmac/")


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def flush_outdated_events(request):
    context_dict = {}
    try:
        enddate = date.today()
        startdate = enddate - timedelta(days=900)
        event_list = Event.objects.filter(date_end__range=[startdate, enddate])
        count = len(event_list)
        print(count)
        for event in event_list:
            print(event.id)
            mydir = os.path.join(settings.MEDIA_ROOT, "event_" + str(event.id))
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
        success_message = str(count) + " мероприятии успешно удалены"
        return show_admin(request, success_message)
    except Exception as e:
        logger.exception("flush_outdated_events failed: %s", e)
        return HttpResponse("Some error occured")
    return render(request, "operator.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
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
        logger.exception("unbind_event failed: %s", e)
        return HttpResponse("Could not find operator")
    return render(request, "operator.html", context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def show_event(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        operators = Operator.objects.filter(events__in=[event])
        reqs = Request.objects.filter(event=event, status__in=["Sent", "Exported"])
        active_reqs = Request.objects.filter(
            event=event, status__in=["Active", "Checking"]
        )
        cities = City.objects.all()
        context_dict = {"events": [event]}
        context_dict["operators"] = operators
        all_operators = Operator.objects.all().order_by("user__last_name")
        other_operators = []
        for a in all_operators:
            if a not in operators:
                other_operators.append(a)
        context_dict["other_operators"] = other_operators
        context_dict["event"] = event
        context_dict["reqs"] = reqs
        context_dict["active_reqs"] = active_reqs
        context_dict["cities"] = cities
        context_dict["unexported"] = len(reqs.exclude(status="Exported"))
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
        print(mydir)
        try:
            shutil.rmtree(mydir)
            print("perfect")
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))
        success_message = "Мероприятие: " + event.name_rus + " успешно удалено"
        event.delete()
        return show_admin(request, success_message)
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
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
        )

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
