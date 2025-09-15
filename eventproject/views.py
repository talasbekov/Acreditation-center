from django.shortcuts import render
from django.http import HttpResponse
from eventproject.models import Event, Operator, Request, Attendee
import datetime
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta, datetime
from django.contrib.auth import logout
from directories.models import Sex, Country, DocumentType, City, Category
from django.forms.models import model_to_dict
from django.contrib.auth.decorators import user_passes_test
from django.http import FileResponse
import json
import secrets
import os
import shutil
from distutils.dir_util import copy_tree
import mimetypes
from django.http import StreamingHttpResponse
from wsgiref.util import FileWrapper
from multiprocessing import Process
from manual import download_photos_async


# from django.core.urlresolvers import reverse


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def index(request):
    # Construct a dictionary to pass to the template engine as its context.
    # Note the key boldmessage is the same as {{ boldmessage }} in the template!
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    event_list = Event.objects.filter(date_end__range=[startdate, enddate]).order_by('date_start')
    operators = Operator.objects.all()
    cities = City.objects.all()
    context_dict = {'events': event_list}
    context_dict['operators'] = operators
    context_dict['cities'] = cities
    return render(request, 'index.html', context=context_dict)


def show_admin(request, success_message):
    # Construct a dictionary to pass to the template engine as its context.
    # Note the key boldmessage is the same as {{ boldmessage }} in the template!
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    event_list = Event.objects.filter(date_end__range=[startdate, enddate]).order_by('date_start')
    operators = Operator.objects.all()
    cities = City.objects.all()
    context_dict = {'events': event_list}
    context_dict['operators'] = operators
    context_dict['success_message'] = success_message
    context_dict['cities'] = cities
    return render(request, 'index.html', context=context_dict)


def show_admin_error(request, error_message):
    # Construct a dictionary to pass to the template engine as its context.
    # Note the key boldmessage is the same as {{ boldmessage }} in the template!
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    event_list = Event.objects.filter(date_end__range=[startdate, enddate]).order_by('date_start')
    operators = Operator.objects.all()
    cities = City.objects.all()
    context_dict = {'events': event_list}
    context_dict['operators'] = operators
    context_dict['error_message'] = error_message
    context_dict['cities'] = cities
    return render(request, 'index.html', context=context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def create_event(request):
    if request.method == 'POST':
        name_rus = request.POST['name_rus']
        name_kaz = request.POST['name_kaz']
        name_eng = request.POST['name_eng']
        event_code = request.POST['event_code']
        date_start = request.POST['date_start']
        date_end = request.POST['date_end']
        city = request.POST['city']
        today = date.today()
        sd = datetime.strptime(date_start, '%Y-%m-%d').date()
        ed = datetime.strptime(date_end, '%Y-%m-%d').date()
        if name_rus == "":
            error_message = "Не удалось создать мероприятие. Название мероприятия отсутствует"
            return show_admin_error(request, error_message)
        if ed < sd:
            error_message = "Не удалось создать мероприятие. Дата окончания не может быть раньше даты создания"
            return show_admin_error(request, error_message)
        if ed < today:
            error_message = "Не удалось создать мероприятие. Истек дата окончания"
            return show_admin_error(request, error_message)
        event = Event(name_kaz=name_kaz, name_rus=name_rus, name_eng=name_eng, event_code=event_code,
                      date_start=date_start, date_end=date_end, city_code=city)
        event.save()
        success_message = "Мероприятие " + name_rus + " успешно создано"
        return show_admin(request, success_message)

    return HttpResponseRedirect('/avmac/')


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def add_operator(request):
    try:
        if request.method == 'POST':
            first_name = request.POST['first_name']
            last_name = request.POST['last_name']
            patronymic = request.POST['patronymic']
            login = request.POST['login']
            phone_number = request.POST['phone_number']
            password = secrets.token_urlsafe(8)
            event_code = request.POST['event_code']
            workplace = request.POST['workplace']

            user = User(username=login,
                        first_name=first_name,
                        last_name=last_name,
                        password=password)
            user.save()
            user.set_password(password)
            user.save()
            event = Event.objects.get(pk=event_code)
            operator = Operator(user=user, phone_number=phone_number, patronymic=patronymic, workplace=workplace)
            operator.save()
            operator.events.add(event)
            operator.save()
            success_message = "Пользователь " + login + " успешно создан! Пароль: " + password
            return show_admin(request, success_message)
    except Exception as e:
        error_message = "Не удалось создать пользователя. Возможно повторояется логин с другим пользователем"
        return show_admin_error(request, error_message)

    return HttpResponseRedirect('/avmac/')


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def bind_operators(request):
    # try:
    if request.method == 'POST':
        operators = request.POST.getlist('operator')
        event_code = request.POST['event_code']

        event = Event.objects.get(id=event_code)
        for o in operators:
            operator = Operator.objects.get(id=o)
            operator.events.add(event)
            operator.save()
        success_message = "Операторы успешно добавлены"
        return HttpResponseRedirect('/show_event/%s/' % event.id)
        # return HttpResponseRedirect('/show_event/', event.id)
    # except Exception as e:
    #     error_message = "Произошла ошибка"
    #     return show_admin_error(request, error_message)

    return HttpResponseRedirect('/avmac/')


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def add_operator_to_event(request):
    try:
        if request.method == 'POST':
            operator_id = request.POST['operator_id']
            event_id = request.POST['event_id']
            operator = Operator.objects.get(id=operator_id)
            event = Event.objects.get(id=event_id)
            operator.events.add(event)
            operator.save()
            success_message = "Пользователью " + operator.user.last_name + " " + operator.user.first_name + " успешно предоставлен доступ на мероприятие " + event.name_rus
            return show_admin(request, success_message)
    except Exception as e:
        error_message = "Не удалось добавить пользователя."
        return show_admin_error(request, error_message)

    return HttpResponseRedirect('/avmac/')


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def show_operator(request, operator_id):
    context_dict = {}
    try:
        operator = Operator.objects.get(pk=operator_id)
        startdate = date.today()
        enddate = startdate + timedelta(days=900)
        event_list = operator.events.filter(date_end__range=[startdate, enddate]).order_by('-date_start')
        reqs = Request.objects.filter(created_by=operator).order_by('-date_created')
        context_dict['events'] = event_list
        context_dict['operator'] = operator
        context_dict['reqs'] = reqs
    except Exception as e:
        return HttpResponse("Could not find operator")
    return render(request, 'operator.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
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
    return render(request, 'operator.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
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
        success_message = str(count) + " мероприятии успешно удалены"
        return show_admin(request, success_message)
    except Exception as e:
        return HttpResponse("Some error occured")
    return render(request, 'operator.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def unbind_event(request, event_id, username):
    context_dict = {}
    try:
        user = User.objects.get(username=username)
        operator = Operator.objects.get(user=user)
        event = Event.objects.get(pk=event_id)
        operator.events.remove(event)
        success_message = event.name_rus + " успешно откреплен от пользователя " + user.last_name + " " + user.first_name
        return show_admin(request, success_message)
    except Exception as e:
        return HttpResponse("Could not find operator")
    return render(request, 'operator.html', context_dict)


@login_required(login_url='/user_login/')
def application(request):
    if not request.user.is_authenticated:
        return HttpResponse("You are logged in.")
    user = request.user
    if user.is_superuser:
        return HttpResponseRedirect('/avmac/')
    operator = Operator.objects.get(user=user)
    cities = City.objects.all()
    if not operator:
        return HttpResponse("You are logged in.")
    startdate = date.today()
    enddate = startdate + timedelta(days=600)
    events = operator.events.filter(date_end__range=[startdate, enddate])
    reqs = Request.objects.filter(created_by=operator).order_by('-date_created')
    return render(request, 'gov2.html',
                  {'user': user, 'operator': operator, 'events': events, 'reqs': reqs, 'cities': cities})


@login_required(login_url='/user_login/')
def create_request(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        context_dict['event'] = event
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
        context_dict['req'] = req
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'request.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
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
        event_list = operator.events.filter(date_end__range=[startdate, enddate]).order_by('-date_start')
        reqs = Request.objects.filter(created_by=operator).order_by('-date_created')
        context_dict['events'] = event_list
        context_dict['operator'] = operator
        context_dict['requests'] = reqs
        context_dict['success_message'] = "Сгенерирован новый пароль: " + password
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'operator.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def show_request_to_admin(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict['req'] = req
        attendees = Attendee.objects.filter(request=req)
        context_dict['attendees'] = attendees
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
        if req.status == "Sent":
            context_dict['delete_message'] = "Отправлено " + str(req.registration_time)
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'request_admin.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def show_event(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        operators = Operator.objects.filter(events__in=[event])
        reqs = Request.objects.filter(event=event, status__in=['Sent', 'Exported'])
        active_reqs = Request.objects.filter(event=event, status__in=['Active', 'Checking'])
        cities = City.objects.all()
        context_dict = {'events': [event]}
        context_dict['operators'] = operators
        all_operators = Operator.objects.all().order_by('user__last_name')
        other_operators = []
        for a in all_operators:
            if a not in operators:
                other_operators.append(a)
        context_dict['other_operators'] = other_operators
        context_dict['event'] = event
        context_dict['reqs'] = reqs
        context_dict['active_reqs'] = active_reqs
        context_dict['cities'] = cities
        context_dict['unexported'] = len(reqs.exclude(status="Exported"))
        zip_name = "event_" + str(event_id) + ".zip"
        if os.path.isfile(zip_name):
            context_dict['file'] = zip_name
            size = os.path.getsize(zip_name)
            context_dict['file_size'] = str(size / 1000000) + " MB"
            ms = os.path.getmtime(zip_name)
            context_dict['file_time'] = datetime.fromtimestamp(ms)
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'event.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def delete_event(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        mydir = "media/event_" + str(event.id)
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
    return render(request, 'event.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def download_json(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        request_set = Request.objects.filter(event=event, status='Sent')
        list_of_requests = []
        print(len(request_set))
        for req in request_set:
            request_dict = model_to_dict(req)
            attendees = Attendee.objects.filter(request=req)
            list_of_attendees = []
            for attendee in attendees:
                attendee_dict = model_to_dict(attendee)
                # attendee_dict['photo'] = attendee.photo.url
                list_of_attendees.append(attendee_dict)
            request_dict['attendees'] = list_of_attendees
            request_dict['event'] = req.event
            request_dict['created_by'] = req.created_by
            list_of_requests.append(request_dict)
            req.status = "Exported"
            req.save()
        event_dict = model_to_dict(event)
        event_dict['requests'] = list_of_requests
        serialized_event = json.dumps(event_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False)
        return HttpResponse(serialized_event, content_type="application/json")
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'event.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def download_guests_json(request, event_id):
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


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def download_all_guests_json(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        request_set = Request.objects.filter(event=event, status__in=['Sent', 'Exported'])
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


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def download_request_json(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(id=request_id)
        request_dict = model_to_dict(req)
        attendees = Attendee.objects.filter(request=req)
        list_of_attendees = []
        for attendee in attendees:
            attendee_dict = model_to_dict(attendee)
            # attendee_dict['photo'] = attendee.photo.url
            list_of_attendees.append(attendee_dict)
        request_dict['attendees'] = list_of_attendees
        request_dict['event'] = req.event
        serialized_event = json.dumps(request_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False)
        req.status = "Exported"
        req.save()
        return HttpResponse(serialized_event, content_type="application/json")
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'event.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def download_photos(request, event_id):
    context_dict = {}
    try:
        if os.path.exists("event_" + str(event_id) + ".zip"):
            os.remove("event_" + str(event_id) + ".zip")
            print("The file has been deleted successfully")
        else:
            print("The file does not exist!")
        dir_name = 'media/event_' + str(event_id)
        if not os.path.isdir(dir_name):
            return HttpResponse("No photos uploaded yet")
        output_filename = "output/event_" + str(event_id) + "/event_" + str(event_id)
        copy_tree(dir_name, output_filename)
        zip_address = "output/event_" + str(event_id)
        file = open(zip_address + "/test.txt", "w")
        file.close()
        archieve = "event_" + str(event_id)
        shutil.make_archive(archieve, 'zip', zip_address)
        zip = open(archieve + '.zip', 'rb')
        response = FileResponse(zip)
        return response
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'event.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def download_file(request, event_id):
    context_dict = {}
    try:
        the_file = 'event_' + str(event_id) + ".zip"
        filename = os.path.basename(the_file)
        chunk_size = 8192
        response = StreamingHttpResponse(FileWrapper(open(the_file, 'rb'), chunk_size),
                                         content_type=mimetypes.guess_type(the_file)[0])
        response['Content-Length'] = os.path.getsize(the_file)
        response['Content-Disposition'] = "attachment; filename=%s" % filename
        return response
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'event.html', context_dict)


@user_passes_test(lambda u: u.is_superuser, login_url='/user_login/')
def prepare_file(request, event_id):
    context_dict = {}
    try:
        p = Process(target=download_photos_async, args=(event_id,))
        p.start()
        context_dict['success_message'] = "Архивируется файлы, через какое-то время обновите страницу"
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'event.html', context_dict)


@login_required(login_url='/user_login/')
def show_request(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict['req'] = req
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        attendees = Attendee.objects.filter(request=req)
        context_dict['attendees'] = attendees
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
        if req.status == "Sent":
            context_dict['success_message'] = "Отправлено " + str(req.registration_time)
        elif req.status == "Checking":
            context_dict['success_message'] = "Заявка готова к отправлению"
            context_dict[
                'delete_message'] = "Внимание!!! Отправка заявки не гарантирует допуск участника в зону проведения охранного мероприятия в установленную дату"
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'request.html', context_dict)


@login_required(login_url='/user_login/')
def preview(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict['req'] = req
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.status = "Checking"
        req.save()
        attendees = Attendee.objects.filter(request=req)
        context_dict['attendees'] = attendees
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
        context_dict['success_message'] = "Заявка готова к отправлению"
        context_dict[
            'delete_message'] = "Внимание!!! Отправка заявки не гарантирует допуск участника в зону проведения охранного мероприятия в установленную дату"
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'request.html', context_dict)


@login_required(login_url='/user_login/')
def back_to_change(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict['req'] = req
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.status = "Active"
        req.save()
        attendees = Attendee.objects.filter(request=req)
        context_dict['attendees'] = attendees
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'request.html', context_dict)


@login_required(login_url='/user_login/')
def send(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict['req'] = req
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.status = "Sent"
        req.registration_time = timezone.now()
        req.save()
        attendees = Attendee.objects.filter(request=req)
        context_dict['attendees'] = attendees
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
        context_dict['success_message'] = "Отправлено " + str(req.registration_time)
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'request.html', context_dict)


@login_required(login_url='/user_login/')
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
    return HttpResponseRedirect('/application/')


@login_required(login_url='/user_login/')
def delete_attendee(request):
    context_dict = {}
    try:
        if request.method == 'POST':
            attendee_id = request.POST['attendee_id']
            attendee = Attendee.objects.get(id=attendee_id)
            req = attendee.request
            operator = Operator.objects.get(user=request.user)
            if req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")
            context_dict['req'] = req
            attendees = Attendee.objects.filter(request=req)
            context_dict['attendees'] = attendees
            countries = Country.objects.all()
            context_dict['countries'] = countries
            document_types = DocumentType.objects.all()
            context_dict['document_types'] = document_types
            sexs = Sex.objects.all()
            context_dict['sexs'] = sexs
            context_dict[
                'delete_message'] = "Участник " + attendee.surname + " " + attendee.firstname + " был успешно удален"
            attendee.delete()
    except Attendee.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'request.html', context_dict)


def check_dublicate(attendee, req):
    attendees = Attendee.objects.filter(request__event=req.event)
    if attendee.countryId == "1000000105":
        fa = attendees.filter(iin=attendee.iin)
    else:
        fa = attendees.filter(surname=attendee.surname, firstname=attendee.firstname, birthDate=attendee.birthDate)
    if len(fa) > 0:
        return True
    else:
        return False


@login_required(login_url='/user_login/')
def delete_attendee_admin(request):
    context_dict = {}
    try:
        if request.method == 'POST':
            attendee_id = request.POST['attendee_id']
            attendee = Attendee.objects.get(id=attendee_id)
            req = attendee.request
            operator = Operator.objects.get(user=request.user)
            if req.created_by == operator:
                return HttpResponse("You are not authorised to see this page")
            context_dict['req'] = req
            attendees = Attendee.objects.filter(request=req)
            context_dict['attendees'] = attendees
            countries = Country.objects.all()
            context_dict['countries'] = countries
            document_types = DocumentType.objects.all()
            context_dict['document_types'] = document_types
            sexs = Sex.objects.all()
            context_dict['sexs'] = sexs
            context_dict[
                'delete_message'] = "Участник " + attendee.surname + " " + attendee.firstname + " был успешно удален"
            attendee.delete()
    except Attendee.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'request_admin.html', context_dict)


@login_required(login_url='/user_login/')
def add_attendee(request, request_id):
    context_dict = {}
    countries = Country.objects.all()
    context_dict['countries'] = countries.order_by('name_rus')
    document_types = DocumentType.objects.all()
    context_dict['document_types'] = document_types
    sexs = Sex.objects.all()
    context_dict['sexs'] = sexs
    categories = Category.objects.all()
    context_dict['categories'] = categories
    if request.method == 'GET':
        try:
            req = Request.objects.get(id=request_id)
            context_dict['req'] = req
            operator = Operator.objects.get(user=request.user)
            if req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")
        except Request.DoesNotExist:
            return HttpResponse("Could not find event")
    elif request.method == 'POST':
        # try:
        rid = request.POST['req_id']
        req = Request.objects.get(id=rid)
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        attendee = Attendee()
        attendee.surname = request.POST['last_name']
        attendee.firstname = request.POST['first_name']
        attendee.patronymic = request.POST['patronymic']
        attendee.transcription = request.POST['latin_name']
        attendee.iin = request.POST['iin']
        attendee.birthDate = request.POST['dob']
        attendee.sexId = request.POST['sex']
        attendee.countryId = request.POST['citizenship']
        attendee.post = request.POST['post']
        attendee.docTypeId = request.POST['document_type']
        attendee.docSeries = request.POST['doc_series']
        attendee.docNumber = request.POST['doc_number']
        attendee.docBegin = request.POST['doc_date_start']
        attendee.docEnd = request.POST['doc_date_end']
        attendee.docIssue = request.POST['doc_issuer']
        attendee.photo = request.FILES['photo']
        # attendee.photo.save()
        attendee.docScan = request.FILES['doc_photo']
        attendee.visitObjects = request.POST['visit_objects']
        attendee.request = req
        attendee.dateAdd = timezone.now()
        attendee.dateEnd = date.today()
        if attendee.countryId != "1000000105aaaa":
            attendee.stickId = request.POST['category']
        doc_start = datetime.strptime(attendee.docBegin, '%Y-%m-%d').date()
        doc_end = datetime.strptime(attendee.docEnd, '%Y-%m-%d').date()
        dob = datetime.strptime(attendee.birthDate, '%Y-%m-%d').date()
        if doc_start > date.today():
            context_dict['delete_message'] = "Не удалось добавить. Дата выдачи документа еще не наступил"
        elif doc_end < date.today():
            context_dict['delete_message'] = "Не удалось добавить. Истек срок документа"
        elif dob > date.today():
            context_dict['delete_message'] = "Не удалось добавить. Проверьте дату рождения"
        elif attendee.photo.size > 9000000:
            context_dict['delete_message'] = "Не удалось добавить. Размер фотографии превышает 7Mb"
        elif attendee.photo.size < 50000:
            context_dict['delete_message'] = "Не удалось добавить. Размер фотографии меньше чем 50Kb"
        elif attendee.docScan.size > 9000000:
            context_dict['delete_message'] = "Не удалось добавить. Размер скана документа превышает 7Mb"
        elif attendee.docScan.size < 50000:
            context_dict['delete_message'] = "Не удалось добавить. Размер скана документа меньше чем 50Kb"
        elif attendee.countryId == "1000000105" and len(attendee.iin) < 12:
            context_dict['delete_message'] = "Не удалось добавить. ИИН обязателен для граждан Казахстана"
        elif check_dublicate(attendee, req):
            context_dict['delete_message'] = "Не удалось добавить. Уже ранее добавляли этого участника"
        else:
            attendee.save()
            context_dict[
                'success_message'] = "Участник " + attendee.surname + " " + attendee.firstname + " был успешно добавлен"
        context_dict['req'] = req
        attendees = Attendee.objects.filter(request=req).order_by('-dateAdd')
        context_dict['attendees'] = attendees
        if 'delete_message' in context_dict:
            return render(request, 'gov3.html', context_dict)
        else:
            return render(request, 'request.html', context_dict)
        # except Exception as e:
        #    return HttpResponse("Could not add a guest")
    return render(request, 'gov3.html', context_dict)


@login_required(login_url='/user_login/')
def create_request2(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        context_dict['event'] = event
        operator = Operator.objects.get(user=request.user)
        request_set = Request.objects.filter(event=event, status='Sent')
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        list_of_requests = []
        for req in request_set:
            request_dict = model_to_dict(req)
            attendees = Attendee.objects.filter(request=req)
            list_of_attendees = []
            for attendee in attendees:
                attendee_dict = model_to_dict(attendee)
                list_of_attendees.append(attendee_dict)
            request_dict['attendees'] = list_of_attendees
            serialized_request = json.dumps(request_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False)
            file = open(request_dict['name'] + '.txt', 'w')
            file.write(serialized_request)
            file.close()
            list_of_requests.append(request_dict)
        # print("ai  m here")
        event_dict = model_to_dict(event)
        event_dict['requests'] = list_of_requests
        serialized_event = json.dumps(event_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False)
        print(serialized_event)
        file = open('event_json.txt', 'w')
        file.write(serialized_event)
        file.close()

    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'gov3.html', context_dict)


@login_required(login_url='/user_login/')
def user_logout(request):
    logout(request)
    return HttpResponseRedirect('/user_login/')


@login_required(login_url='/user_login/')
def change_password(request):
    context_dict = {}
    try:
        if request.method == 'POST':
            old_password = request.POST['old_password']
            new_password = request.POST['new_password']
            new_password_repeat = request.POST['new_password_repeat']
            if new_password != new_password_repeat:
                context_dict['error_message'] = "Введите новый пароль два раза"
                return render(request, 'change_password_result.html', context_dict)
            if request.user.check_password(old_password):
                request.user.set_password(new_password)
                request.user.save()
                context_dict['success_message'] = "Пароль успешно изменен"
                return render(request, 'change_password_result.html', context_dict)
            else:
                context_dict['error_message'] = "Не удалось подтвердить данные"
                return render(request, 'change_password_result.html', context_dict)
    except Exception as e:
        print("unknown")
    return render(request, 'change_password.html', context_dict)


def user_login(request):
    context = RequestContext(request)
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                if user.is_superuser:
                    return HttpResponseRedirect('/avmac/')
                else:
                    return HttpResponseRedirect('/application/')
            else:
                return HttpResponse("Your account is suspended")
        else:
            return render(request, 'gov.html', context={'error_message': 'Неправильный логин или пароль'})
    return render(request, 'gov.html', context={})
# return render_to_response('gov.html', , context)
