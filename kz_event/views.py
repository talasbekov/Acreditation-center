from django.shortcuts import render
from django.http import HttpResponse, HttpResponseForbidden
from eventproject.models import Event, Operator, Request, Attendee
from eventproject.view_helpers import require_operator
from django.utils import timezone
import datetime
import logging
from django.http import HttpResponseRedirect

from django.contrib.auth import authenticate, login
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django_ratelimit.decorators import ratelimit
from datetime import date, timedelta, datetime
from django.contrib.auth import logout
from directories.models import Sex, Country, DocumentType, City, Category
from eventproject.validators.iin import event_has_iin_duplicate
from eventproject.validators.residency import resolve_residency

logger = logging.getLogger("eventproject")
import eventproject.views.attendee as attendee_views


# Create your views here.
def user_login(request):
    context = RequestContext(request)
    if request.method == 'POST':
        # P1-2: malformed POST без полей не должен падать KeyError'ом/500.
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                if user.is_superuser:
                    return HttpResponseRedirect('/avmac/')
                else:
                    return HttpResponseRedirect('/kz/application/')
            else:
                return HttpResponse("Your account is suspended")
        else:
            return render(request, 'kz/gov.html', context={'error_message': 'Логин, не құпиясыз сәйкес келмейді'})
    return render(request, 'kz/gov.html', context={})

@login_required(login_url='/kz/user_login/')
def application(request):
    if not request.user.is_authenticated:
        return HttpResponse("You are logged in.")
    user = request.user
    if user.is_superuser:
        return HttpResponseRedirect('/avmac/')
    operator = require_operator(user)
    cities = City.objects.all()
    if not operator:
        return HttpResponse("You are logged in.")
    startdate = date.today()
    enddate = startdate + timedelta(days=600)
    events = operator.events.filter(date_end__range=[startdate, enddate])
    reqs = Request.objects.filter(created_by = operator).order_by('-date_created')
    return render(request, 'kz/gov2.html', {'user': user, 'operator': operator, 'events': events, 'reqs':reqs, 'cities':cities})

@login_required(login_url='/kz/user_login/')
def user_logout(request):
    logout(request)
    return HttpResponseRedirect('/kz/user_login/')

@login_required(login_url='/kz/user_login/')
def change_password(request):
    context_dict = {}
    try:
        if request.method == 'POST':
            old_password = request.POST['old_password']
            new_password = request.POST['new_password']
            new_password_repeat = request.POST['new_password_repeat']
            if new_password != new_password_repeat:
                context_dict['error_message'] = "Жаңа құпиясөздер сәйкес келмейді"
                return render(request, 'kz/change_password_result.html', context_dict)
            if request.user.check_password(old_password):
                request.user.set_password(new_password)
                request.user.save()
                context_dict['success_message'] = "Құпиясөз сәтті өзгертілді"
                return render(request, 'kz/change_password_result.html', context_dict)
            else:
                context_dict['error_message'] = "Ескі құпиясөз дұрыс емес"
                return render(request, 'kz/change_password_result.html', context_dict)
    except Exception as e:
        logger.error("kz change_password failed for user=%s: %s", getattr(request.user, "id", None), e)
        context_dict['error_message'] = "Құпиясөзді өзгерту мүмкін болмады. Қайталап көріңіз."
    return render(request, 'kz/change_password.html', context_dict)

@login_required(login_url='/kz/user_login/')
def create_request(request, event_id):
    context_dict = {}
    try:
        event = Event.objects.get(pk=event_id)
        context_dict['event'] = event
        operator = require_operator(request.user)
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
    return render(request, 'kz/request.html', context_dict)

@login_required(login_url='/kz/user_login/')
def show_request(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict['req'] = req
        operator = require_operator(request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        attendees = Attendee.objects.filter(request = req)
        context_dict['attendees'] = attendees
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
        if req.status == "Sent":
            context_dict['success_message'] = str(req.registration_time)+" жіберілді"
        elif req.status == "Checking":
            context_dict['success_message'] = "Өтініш жіберуге дайын"
            context_dict['delete_message'] = "Назар аударыңыз!!! Өтініштің жіберілімі шараға кіргізілуге кепіл болмайды"
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'kz/request.html', context_dict)


def check_dublicate(attendee, req):
    attendees = Attendee.objects.filter(request__event = req.event)
    if attendee.countryId == "1000000105":
        return event_has_iin_duplicate(attendees, attendee.iin, exclude_pk=attendee.pk)
    else:
        fa = attendees.filter(surname=attendee.surname, firstname=attendee.firstname, birthDate=attendee.birthDate)
        if attendee.pk:
            fa = fa.exclude(pk=attendee.pk)
    return fa.exists()

@ratelimit(key="ip", rate="20/h", method="POST", block=True)
@login_required(login_url='/kz/user_login/')
def add_attendee(request, request_id):
    context_dict = {}
    countries = Country.objects.all()
    context_dict['countries'] = countries.order_by('name_kaz')
    document_types = DocumentType.objects.all()
    context_dict['document_types'] = document_types
    sexs = Sex.objects.all()
    context_dict['sexs'] = sexs
    categories = Category.objects.all()
    context_dict['categories'] = categories
    if request.method == 'GET':
        try:
            req = Request.objects.get(id = request_id)
            context_dict['req'] = req
            operator = require_operator(request.user)
            if req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")
        except Request.DoesNotExist:
            return HttpResponse("Could not find event")
        except Operator.DoesNotExist:
            return HttpResponseForbidden("Operator profile not found.")
    elif request.method == 'POST':
        #try:
        rid = request.POST['req_id']
        req = Request.objects.get(id = rid)
        try:
            operator = require_operator(request.user)
        except Operator.DoesNotExist:
            return HttpResponseForbidden("Operator profile not found.")
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        attendee = Attendee()
        attendee.surname = request.POST.get("last_name", "")
        attendee.firstname= request.POST.get("first_name", "")
        attendee.patronymic = request.POST.get("patronymic", "")
        attendee.transcription = request.POST.get("latin_name", "")
        attendee.iin = request.POST.get('iin', '').strip()
        attendee.birthDate = request.POST.get("dob", "")
        attendee.sexId = request.POST.get("sex", "")
        attendee.countryId = request.POST.get('citizenship', '')
        attendee.post = request.POST.get("post", "")
        attendee.docTypeId = request.POST.get("document_type", "")
        attendee.docSeries = request.POST.get("doc_series", "")
        attendee.docNumber = request.POST.get("doc_number", "")
        attendee.docBegin = request.POST.get("doc_date_start", "")
        attendee.docEnd = request.POST.get("doc_date_end", "")
        attendee.docIssue = request.POST.get("doc_issuer", "")
        attendee.photo = request.FILES['photo']
        #attendee.photo.save()
        attendee.docScan = request.FILES['doc_photo']
        attendee.visitObjects = request.POST.get("visit_objects", "")
        attendee.request = req
        attendee.dateAdd = timezone.now()
        attendee.dateEnd = date.today()
        if attendee.countryId != "1000000105":
            attendee.stickId = request.POST.get('category', '')
        # P1-3: битая дата из прямого POST больше не 500.
        try:
            doc_start = datetime.strptime(attendee.docBegin, '%Y-%m-%d').date()
            doc_end = datetime.strptime(attendee.docEnd, '%Y-%m-%d').date()
            dob = datetime.strptime(attendee.birthDate, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            context_dict['delete_message'] = "Қатысушы қосылмады. Күн форматын тексеріңіз (ЖЖЖЖ-АА-КК)."
            context_dict['req'] = req
            context_dict['attendees'] = Attendee.objects.filter(request=req)
            return render(request, 'kz/gov3.html', context_dict)
        # Story 3.5: единый residency+ИИН-валидатор (validators/iin.py).
        residency = resolve_residency(attendee.countryId, attendee.iin, dob)
        attendee.iin = residency.iin
        attendee.is_resident = residency.is_resident
        if doc_start>date.today():
            context_dict['delete_message'] = "Қатысушы қосылмады. Құжаттың берілген күні қате"
            #return render(request, 'request.html', context_dict)
        elif doc_end<date.today():
            context_dict['delete_message'] = "Қатысушы қосылмады. Құжаттың мерзімі өтіп кетті"
            #return render(request, 'request.html', context_dict)
        elif dob>date.today():
            context_dict['delete_message'] = "Қатысушы қосылмады. Туған күн қате еңгізілген"
            #return render(request, 'request.html', context_dict)
        elif attendee.photo.size > 9000000:
            context_dict['delete_message'] = "Қатысушы қосылмады. Суреттің салмағы 7Mb артады"
            #return render(request, 'request.html', context_dict)
        elif attendee.docScan.size > 9000000:
            context_dict['delete_message'] = "Қатысушы қосылмады. Құжаттың салмағы 7Mb артады"
            #return render(request, 'request.html', context_dict)
        elif attendee.photo.size < 1000:
            context_dict['delete_message'] = "Қатысушы қосылмады. Суреттің салмағы кемінде 1Kb болуы қажет"
        elif attendee.docScan.size < 1000:
            context_dict['delete_message'] = "Қатысушы қосылмады. Құжаттың салмағы кемінде 1Kb болуы қажет"
        elif residency.error:
            context_dict['delete_message'] = residency.error
            context_dict['iin_error'] = residency.error
        elif check_dublicate(attendee, req):
            context_dict['delete_message'] = "Қатысушы қосылмады. Қатысушыны қайтара қосып жатырсыз"
        else:
            attendee.save()
            attendee_views.audit_log(
                user=request.user if request.user.is_authenticated else None,
                action="attendee.create",
                obj_type="Attendee",
                obj_id=attendee.id,
                ip=request.META.get("REMOTE_ADDR"),
            )
            context_dict['success_message'] = "Қатысушы " + attendee.surname + " " + attendee.firstname + " сәтті қосылды"
        context_dict['req'] = req
        attendees = Attendee.objects.filter(request=req).order_by('-dateAdd')
        context_dict['attendees'] = attendees
        context_dict['form_data'] = request.POST
        if 'delete_message' in context_dict:
            return render(request, 'kz/gov3.html', context_dict)
        else:
            return render(request, 'kz/request.html', context_dict)
        #except Exception as e:
        #    return HttpResponse("Could not add a guest")
    return render(request, 'kz/gov3.html', context_dict)

@login_required(login_url='/kz/user_login/')
def back_to_change(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict['req'] = req
        operator = require_operator(request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.status = "Active"
        req.save()
        attendees = Attendee.objects.filter(request = req)
        context_dict['attendees'] = attendees
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'kz/request.html', context_dict)

@login_required(login_url='/kz/user_login/')
def preview(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict['req'] = req
        operator = require_operator(request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.status = "Checking"
        req.save()
        attendees = Attendee.objects.filter(request = req)
        context_dict['attendees'] = attendees
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
        context_dict['success_message'] = "Өтініш жіберуге дайын"
        context_dict['delete_message'] = "Назар аударыңыз!!! Өтініштің жіберілімі шараға кіргізілуге кепіл болмайды"
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'kz/request.html', context_dict)

@login_required(login_url='/user_login/')
def send(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        context_dict['req'] = req
        operator = require_operator(request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        req.status = "Sent"
        req.registration_time = timezone.now()
        req.save()
        attendees = Attendee.objects.filter(request = req)
        context_dict['attendees'] = attendees
        countries = Country.objects.all()
        context_dict['countries'] = countries
        document_types = DocumentType.objects.all()
        context_dict['document_types'] = document_types
        sexs = Sex.objects.all()
        context_dict['sexs'] = sexs
        context_dict['success_message'] = str(req.registration_time)+" жіберілді"
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'kz/request.html', context_dict)

@login_required(login_url='/kz/user_login/')
def delete_attendee(request):
    context_dict = {}
    try:
        if request.method == 'POST':
            attendee_id = request.POST['attendee_id']
            attendee = Attendee.objects.get(id = attendee_id)
            req = attendee.request
            operator = require_operator(request.user)
            if req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")
            attendee_views.audit_log(
                user=request.user if request.user.is_authenticated else None,
                action="attendee.delete",
                obj_type="Attendee",
                obj_id=str(attendee_id),
                ip=request.META.get("REMOTE_ADDR"),
            )
            context_dict['req'] = req
            attendees = Attendee.objects.filter(request=req)
            context_dict['attendees'] = attendees
            countries = Country.objects.all()
            context_dict['countries'] = countries
            document_types = DocumentType.objects.all()
            context_dict['document_types'] = document_types
            sexs = Sex.objects.all()
            context_dict['sexs'] = sexs
            context_dict['delete_message'] = "Қатысушы "+attendee.surname + " " +attendee.firstname +" жүйеден өшірілді"
            attendee.delete()
    except Attendee.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, 'kz/request.html', context_dict)

@login_required(login_url='/kz/user_login/')
@require_POST
@csrf_protect
def delete_request(request, request_id):
    context_dict = {}
    try:
        req = Request.objects.get(pk=request_id)
        user = request.user
        if not user.is_superuser:
            operator = require_operator(user)
            if req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")
        req.delete()
    except Request.DoesNotExist:
        return HttpResponse("Could not find request", status=404)
    return HttpResponseRedirect('/kz/application/')
