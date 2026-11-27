from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from directories.models import Sex, Country, DocumentType, Category
from eventproject.view_helpers import assigned_event, owned_request, require_operator
from eventproject.models import Event, Operator, Request, Attendee
from eventproject.services.lifecycle import local_time
from eventproject import page_lang


def _request_page_context(req, **extra):
    """Контекст страницы заявки: участники и справочники для подписей."""
    context = {
        "req": req,
        "attendees": Attendee.objects.filter(request=req),
        "countries": Country.objects.all(),
        "categories": Category.objects.all(),
        "document_types": DocumentType.objects.all(),
        "sexs": Sex.objects.all(),
    }
    context.update(extra)
    return context


@page_lang.login_required
@require_POST
@csrf_protect
def create_request(request, event_id, lang="ru"):
    context_dict = {}
    try:
        event = assigned_event(request.user, event_id)
        context_dict["event"] = event
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
        context_dict["req"] = req
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, page_lang.template(lang, "request.html"), context_dict)


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
            context_dict["delete_message"] = "Отправлено " + local_time(req.registration_time)
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "request_admin.html", context_dict)


@page_lang.login_required
def show_request(request, request_id, lang="ru"):
    try:
        req = owned_request(request.user, request_id)
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    extra = {}
    if req.status == "Sent":
        extra["success_message"] = page_lang.text("sent_at", lang, time=local_time(req.registration_time))
    return render(request, page_lang.template(lang, "request.html"), _request_page_context(req, **extra))


@page_lang.login_required
@require_POST
@csrf_protect
def delete_request(request, request_id, lang="ru"):
    try:
        if request.user.is_superuser:
            req = get_object_or_404(Request, pk=request_id)
        else:
            req = owned_request(request.user, request_id)
        req.delete()
    except Request.DoesNotExist:
        return HttpResponse("Could not find request", status=404)
    return HttpResponseRedirect(page_lang.url(lang, "/application/"))


@login_required(login_url="/user_login/")
def create_request2(request, event_id):
    context_dict = {}
    try:
        event = assigned_event(request.user, event_id)
        context_dict["event"] = event
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
        countries = Country.objects.all()
        context_dict["countries"] = countries
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
    except Event.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "gov3.html", context_dict)
