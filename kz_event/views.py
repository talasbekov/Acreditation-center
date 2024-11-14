from django.shortcuts import render
from django.http import HttpResponse
from eventproject.models import Event, Operator, Request, Attendee
import datetime
from django.http import HttpResponseRedirect
from django.contrib.auth import authenticate, login
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta
from django.contrib.auth import logout
from directories.models import Sex, Country, DocumentType, City, Category


# Create your views here.
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
                    return HttpResponseRedirect("/kz/application/")
            else:
                return HttpResponse("Your account is suspended")
        else:
            return render(
                request,
                "kz/gov.html",
                context={"error_message": "Логин, не құпиясыз сәйкес келмейді"},
            )
    return render(request, "kz/gov.html", context={})


@login_required(login_url="/kz/user_login/")
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
        "kz/gov2.html",
        {
            "user": user,
            "operator": operator,
            "events": events,
            "reqs": reqs,
            "cities": cities,
        },
    )


@login_required(login_url="/kz/user_login/")
def user_logout(request):
    logout(request)
    return HttpResponseRedirect("/kz/user_login/")


@login_required(login_url="/kz/user_login/")
def change_password(request):
    context_dict = {}
    try:
        if request.method == "POST":
            old_password = request.POST["old_password"]
            new_password = request.POST["new_password"]
            new_password_repeat = request.POST["new_password_repeat"]
            if new_password != new_password_repeat:
                context_dict["error_message"] = "Жаңа құпиясөздер сәйкес келмейді"
                return render(request, "kz/change_password_result.html", context_dict)
            if request.user.check_password(old_password):
                request.user.set_password(new_password)
                request.user.save()
                context_dict["success_message"] = "Құпиясөз сәтті өзгертілді"
                return render(request, "kz/change_password_result.html", context_dict)
            else:
                context_dict["error_message"] = "Ескі құпиясөз дұрыс емес"
                return render(request, "kz/change_password_result.html", context_dict)
    except Exception:
        print("unknown")
    return render(request, "kz/change_password.html", context_dict)


@login_required(login_url="/kz/user_login/")
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
    return render(request, "kz/request.html", context_dict)


@login_required(login_url="/kz/user_login/")
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
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
        if req.status == "Sent":
            context_dict["success_message"] = str(req.registration_time) + " жіберілді"
        elif req.status == "Checking":
            context_dict["success_message"] = "Өтініш жіберуге дайын"
            context_dict["delete_message"] = (
                "Назар аударыңыз!!! Өтініштің жіберілімі шараға кіргізілуге кепіл болмайды"
            )
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "kz/request.html", context_dict)


def check_dublicate(attendee, req):
    attendees = Attendee.objects.filter(request__event=req.event)
    if attendee.countryId == "1000000105":
        fa = attendees.filter(iin=attendee.iin)
    else:
        fa = attendees.filter(
            surname=attendee.surname,
            firstname=attendee.firstname,
            birthDate=attendee.birthDate,
        )
    if len(fa) > 0:
        return True
    else:
        return False


@login_required(login_url="/kz/user_login/")
def add_attendee(request, request_id):
    context_dict = {}
    countries = Country.objects.all()
    context_dict["countries"] = countries.order_by("name_kaz")
    document_types = DocumentType.objects.all()
    context_dict["document_types"] = document_types
    sexs = Sex.objects.all()
    context_dict["sexs"] = sexs
    categories = Category.objects.all()
    context_dict["categories"] = categories
    if request.method == "GET":
        try:
            req = Request.objects.get(id=request_id)
            context_dict["req"] = req
            operator = Operator.objects.get(user=request.user)
            if req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")
        except Request.DoesNotExist:
            return HttpResponse("Could not find event")
    elif request.method == "POST":
        # try:
        rid = request.POST["req_id"]
        req = Request.objects.get(id=rid)
        operator = Operator.objects.get(user=request.user)
        if req.created_by != operator:
            return HttpResponse("You are not authorised to see this page")
        attendee = Attendee()
        attendee.surname = request.POST["last_name"]
        attendee.firstname = request.POST["first_name"]
        attendee.patronymic = request.POST["patronymic"]
        attendee.transcription = request.POST["latin_name"]
        attendee.iin = request.POST["iin"]
        attendee.birthDate = request.POST["dob"]
        attendee.sexId = request.POST["sex"]
        attendee.countryId = request.POST["citizenship"]
        attendee.post = request.POST["post"]
        attendee.docTypeId = request.POST["document_type"]
        attendee.docSeries = request.POST["doc_series"]
        attendee.docNumber = request.POST["doc_number"]
        attendee.docBegin = request.POST["doc_date_start"]
        attendee.docEnd = request.POST["doc_date_end"]
        attendee.docIssue = request.POST["doc_issuer"]
        attendee.photo = request.FILES["photo"]
        # attendee.photo.save()
        attendee.docScan = request.FILES["doc_photo"]
        attendee.visitObjects = request.POST["visit_objects"]
        attendee.request = req
        attendee.dateAdd = datetime.now()
        attendee.dateEnd = date.today()
        if attendee.countryId != "1000000105aaaaa":
            attendee.stickId = request.POST["category"]
        doc_start = datetime.strptime(attendee.docBegin, "%Y-%m-%d").date()
        doc_end = datetime.strptime(attendee.docEnd, "%Y-%m-%d").date()
        dob = datetime.strptime(attendee.birthDate, "%Y-%m-%d").date()
        if doc_start > date.today():
            context_dict["delete_message"] = (
                "Қатысушы қосылмады. Құжаттың берілген күні қате"
            )
            # return render(request, 'request.html', context_dict)
        elif doc_end < date.today():
            context_dict["delete_message"] = (
                "Қатысушы қосылмады. Құжаттың мерзімі өтіп кетті"
            )
            # return render(request, 'request.html', context_dict)
        elif dob > date.today():
            context_dict["delete_message"] = (
                "Қатысушы қосылмады. Туған күн қате еңгізілген"
            )
            # return render(request, 'request.html', context_dict)
        elif attendee.photo.size > 9000000:
            context_dict["delete_message"] = (
                "Қатысушы қосылмады. Суреттің салмағы 7Mb артады"
            )
            # return render(request, 'request.html', context_dict)
        elif attendee.docScan.size > 9000000:
            context_dict["delete_message"] = (
                "Қатысушы қосылмады. Құжаттың салмағы 7Mb артады"
            )
            # return render(request, 'request.html', context_dict)
        elif attendee.photo.size < 50000:
            context_dict["delete_message"] = (
                "Қатысушы қосылмады. Суреттің салмағы кемінде 50Kb болуы қажет"
            )
        elif attendee.docScan.size < 50000:
            context_dict["delete_message"] = (
                "Қатысушы қосылмады. Құжаттың салмағы кемінде 50Kb болуы қажет"
            )
        elif attendee.countryId == "1000000105" and len(attendee.iin) < 12:
            context_dict["delete_message"] = (
                "Қатысушы қосылмады. Қазақстан азаматтарына ЖСН міндетті"
            )
        elif check_dublicate(attendee, req):
            context_dict["delete_message"] = (
                "Қатысушы қосылмады. Қатысушыны қайтара қосып жатырсыз"
            )
        else:
            attendee.save()
            context_dict["success_message"] = (
                "Қатысушы "
                + attendee.surname
                + " "
                + attendee.firstname
                + " сәтті қосылды"
            )
        context_dict["req"] = req
        attendees = Attendee.objects.filter(request=req).order_by("-dateAdd")
        context_dict["attendees"] = attendees
        if "delete_message" in context_dict:
            return render(request, "kz/gov3.html", context_dict)
        else:
            return render(request, "kz/request.html", context_dict)
        # except Exception as e:
        #    return HttpResponse("Could not add a guest")
    return render(request, "kz/gov3.html", context_dict)


@login_required(login_url="/kz/user_login/")
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
    return render(request, "kz/request.html", context_dict)


@login_required(login_url="/kz/user_login/")
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
        context_dict["success_message"] = "Өтініш жіберуге дайын"
        context_dict["delete_message"] = (
            "Назар аударыңыз!!! Өтініштің жіберілімі шараға кіргізілуге кепіл болмайды"
        )
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "kz/request.html", context_dict)


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
        context_dict["success_message"] = str(req.registration_time) + " жіберілді"
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "kz/request.html", context_dict)


@login_required(login_url="/kz/user_login/")
def delete_attendee(request):
    context_dict = {}
    try:
        if request.method == "POST":
            attendee_id = request.POST["attendee_id"]
            attendee = Attendee.objects.get(id=attendee_id)
            req = attendee.request
            operator = Operator.objects.get(user=request.user)
            if req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")
            context_dict["req"] = req
            attendees = Attendee.objects.filter(request=req)
            context_dict["attendees"] = attendees
            countries = Country.objects.all()
            context_dict["countries"] = countries
            document_types = DocumentType.objects.all()
            context_dict["document_types"] = document_types
            sexs = Sex.objects.all()
            context_dict["sexs"] = sexs
            context_dict["delete_message"] = (
                "Қатысушы "
                + attendee.surname
                + " "
                + attendee.firstname
                + " жүйеден өшірілді"
            )
            attendee.delete()
    except Attendee.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "kz/request.html", context_dict)


@login_required(login_url="/kz/user_login/")
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
    return HttpResponseRedirect("/kz/application/")
