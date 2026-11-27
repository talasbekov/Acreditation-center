from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.views.decorators.http import require_POST

import logging
from datetime import date, datetime

from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django_ratelimit.decorators import ratelimit

from directories.models import Sex, Country, DocumentType, Category
from eventproject.view_helpers import owned_attendee, owned_request
from eventproject.models import Operator, Request, Attendee
from eventproject.validators.residency import resolve_residency
from eventproject.audit import audit_log
from eventproject.services import intake, lifecycle
from eventproject import page_lang
from eventproject.views.request import _request_page_context

logger = logging.getLogger("eventproject")


def _ratelimit_response():
    return HttpResponse("Too many requests. Please try again later.", status=429)


def _locked_response(lang):
    return HttpResponse(lifecycle.text("locked", lang), status=409, content_type="text/plain; charset=utf-8")


def _closed_response(lang):
    return HttpResponse(lifecycle.text("closed", lang), status=409, content_type="text/plain; charset=utf-8")


# Этап D: имена полей HTML-формы → поля участника. Формы добавления и правки — один
# шаблон (`_attendee_fields.html`), значения полей готовит `_form_values`.
_FORM_FIELDS = {
    "last_name": "surname", "first_name": "firstname", "patronymic": "patronymic",
    "latin_name": "transcription", "citizenship": "countryId", "iin": "iin", "dob": "birthDate",
    "sex": "sexId", "category": "stickId", "post": "post", "document_type": "docTypeId",
    "doc_series": "docSeries", "doc_number": "docNumber", "doc_date_start": "docBegin",
    "doc_date_end": "docEnd", "doc_issuer": "docIssue", "visit_objects": "visitObjects",
}
_FORM_DEFAULTS = {"citizenship": "1000000105", "document_type": "1000000003"}


def _form_values(post=None, attendee=None):
    """Значения полей формы: введённые (после ошибки), участника (правка) или по умолчанию."""
    if post is not None:
        return {name: post.get(name, "") for name in _FORM_FIELDS}
    if attendee is None:
        return {name: _FORM_DEFAULTS.get(name, "") for name in _FORM_FIELDS}
    values = {}
    for name, attr in _FORM_FIELDS.items():
        value = getattr(attendee, attr, None)
        if hasattr(value, "strftime"):
            value = value.strftime("%Y-%m-%d")
        values[name] = "" if value is None else str(value)
    return values


def _update_attendee_context(attendee, lang="ru"):
    return {
        "attendee": attendee,
        "fv": _form_values(attendee=attendee),
        # Заголовок формы показывает мероприятие заявки (раньше `req` не передавался).
        "req": attendee.request,
        "countries": Country.objects.all().order_by(page_lang.NAME_FIELD[page_lang.norm(lang)]),
        "document_types": DocumentType.objects.all(),
        "sexs": Sex.objects.all(),
        "categories": Category.objects.all(),
    }


def _csrf_missing(request):
    return request.method == "POST" and not (
        request.POST.get("csrfmiddlewaretoken")
        or request.META.get("HTTP_X_CSRFTOKEN")
    )


@page_lang.login_required
@require_POST
@csrf_protect
def delete_attendee(request, lang="ru"):
    try:
        attendee_id = request.POST.get("attendee_id")
        if not attendee_id:
            return HttpResponse("No attendee ID provided", status=400)

        user = request.user
        if user.is_superuser:
            attendee = get_object_or_404(Attendee, pk=attendee_id)
        else:
            attendee = owned_attendee(user, attendee_id)
        req = attendee.request
        if not lifecycle.can_modify(user, attendee):
            return _locked_response(lang)

        attendee.delete()
        audit_log(
            user=request.user if request.user.is_authenticated else None,
            action="attendee.delete",
            obj_type="Attendee",
            obj_id=attendee_id,
            ip=request.META.get("REMOTE_ADDR"),
        )

        # Последний участник — заявка удаляется вместе с ним.
        if not Attendee.objects.filter(request=req).exists():
            req.delete()
            # Объекта в БД больше нет: статус только для шаблона — без кнопок
            # «Добавить» / «Предпросмотр», ведущих на несуществующую заявку.
            req.status = "Deleted"
            context_dict = {
                "req": req,
                "attendees": [],
                "delete_message": page_lang.text("request_deleted", lang, name=req.name),
            }
        else:
            context_dict = _request_page_context(
                req, delete_message=page_lang.text("deleted", lang, surname=attendee.surname, firstname=attendee.firstname),
            )
    except Attendee.DoesNotExist:
        return HttpResponse("Attendee not found", status=404)
    except (Http404, PermissionDenied):
        raise
    except Exception:
        logger.error("delete_attendee failed")
        return HttpResponse(page_lang.text("delete_failed", lang), status=500)

    if user.is_superuser:
        return render(request, "request_admin.html", context_dict)
    return render(request, page_lang.template(lang, "request.html"), context_dict)


@ratelimit(key="ip", rate="20/h", method="POST", block=False)
@csrf_protect
@page_lang.login_required
def add_attendee(request, request_id, lang="ru"):
    if getattr(request, "limited", False):
        return _ratelimit_response()
    if _csrf_missing(request):
        return HttpResponseForbidden("CSRF verification failed. Request aborted.")
    form_template = page_lang.template(lang, "gov3.html")
    context_dict = {
        "countries": Country.objects.all().order_by(page_lang.NAME_FIELD[page_lang.norm(lang)]),
        "document_types": DocumentType.objects.all(),
        "sexs": Sex.objects.all(),
        "categories": Category.objects.all(),
        "fv": _form_values(),
    }
    if request.method == "GET":
        try:
            req = owned_request(request.user, request_id)
            context_dict["req"] = req
        except Request.DoesNotExist:
            return HttpResponse("Could not find event")
        except Operator.DoesNotExist:
            return HttpResponseForbidden("Operator profile not found.")
        if not lifecycle.can_add_to(req):
            return _closed_response(lang)
        return render(request, form_template, context_dict)

    if request.user.is_superuser:
        req = get_object_or_404(Request, pk=request_id)
    else:
        req = owned_request(request.user, request_id)
    if not lifecycle.can_add_to(req):
        return _closed_response(lang)
    attendee = Attendee()
    attendee.surname = request.POST.get("last_name", "")
    attendee.firstname = request.POST.get("first_name", "")
    attendee.patronymic = request.POST.get("patronymic", "")
    attendee.transcription = request.POST.get("latin_name", "")
    attendee.iin = request.POST.get("iin", "").strip()
    attendee.birthDate = request.POST.get("dob", "")
    attendee.sexId = request.POST.get("sex", "")
    attendee.countryId = request.POST.get("citizenship", "")
    attendee.post = request.POST.get("post", "")
    attendee.docTypeId = request.POST.get("document_type", "")
    attendee.docSeries = request.POST.get("doc_series", "")
    attendee.docNumber = request.POST.get("doc_number", "")
    attendee.docBegin = request.POST.get("doc_date_start", "")
    attendee.docEnd = request.POST.get("doc_date_end", "")
    attendee.docIssue = request.POST.get("doc_issuer", "")
    attendee.visitObjects = request.POST.get("visit_objects", "")
    attendee.request = req
    attendee.dateAdd = timezone.now()
    attendee.dateEnd = date.today()
    # P1-4: для резидента РК (id 1000000105) категория скрыта формой и не читается.
    if attendee.countryId != "1000000105":
        attendee.stickId = request.POST.get("category", "")
    context_dict["req"] = req
    # Story 3.5 (AC-2): сохранить введённые данные при ошибке.
    context_dict["form_data"] = request.POST
    context_dict["fv"] = _form_values(post=request.POST)

    def failed(reason, **extra):
        context_dict["delete_message"] = page_lang.text("add_failed", lang, reason=reason)
        context_dict.update(extra)
        context_dict["attendees"] = Attendee.objects.filter(request=req).order_by("-dateAdd")
        return render(request, form_template, context_dict)

    # P1-3: битая дата из прямого POST (минуя <input type=date>) больше не 500.
    try:
        doc_start = datetime.strptime(attendee.docBegin, "%Y-%m-%d").date()
        doc_end = datetime.strptime(attendee.docEnd, "%Y-%m-%d").date()
        dob = datetime.strptime(attendee.birthDate, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return failed(page_lang.text("bad_date_format", lang))
    # Story 3.5: единый residency+ИИН-валидатор (validators/iin.py).
    residency = resolve_residency(attendee.countryId, attendee.iin, dob)
    attendee.iin = residency.iin
    attendee.is_resident = residency.is_resident
    if doc_start > date.today():
        return failed(page_lang.text("doc_not_started", lang))
    if doc_end < date.today():
        return failed(page_lang.text("doc_expired", lang))
    if dob > date.today():
        return failed(page_lang.text("dob_future", lang))
    if residency.error:
        iin_error = page_lang.residency_error(residency, lang)
        return failed(iin_error, iin_error=iin_error)
    upload_error = intake.apply_uploads(attendee, request.FILES, lang)
    if upload_error:
        return failed(upload_error)
    duplicate = intake.save_unless_duplicate(attendee, req.event_id)
    if duplicate:
        return failed(intake.duplicate_text(duplicate, lang))

    audit_log(
        user=request.user if request.user.is_authenticated else None,
        action="attendee.create",
        obj_type="Attendee",
        obj_id=attendee.id,
        ip=request.META.get("REMOTE_ADDR"),
    )
    context_dict["success_message"] = page_lang.text(
        "added", lang, surname=attendee.surname, firstname=attendee.firstname, transcription=attendee.transcription,
    )
    context_dict["attendees"] = Attendee.objects.filter(request=req).order_by("-dateAdd")
    return render(request, page_lang.template(lang, "request.html"), context_dict)


@ratelimit(key="ip", rate="20/h", method="POST", block=False)
@csrf_protect
@page_lang.login_required
def update_attendee(request, attendee_id, lang="ru"):
    context_dict = {}
    if getattr(request, "limited", False):
        return _ratelimit_response()
    if _csrf_missing(request):
        return HttpResponseForbidden("CSRF verification failed. Request aborted.")
    try:
        user = request.user
        if user.is_superuser or user.role == "superoperator":
            attendee = get_object_or_404(Attendee, pk=attendee_id)
        else:
            attendee = owned_attendee(user, attendee_id)
        req = attendee.request
        if not lifecycle.can_modify(user, attendee):
            return _locked_response(lang)

        if request.method == "GET":
            context_dict.update(_update_attendee_context(attendee, lang))
            return render(request, "update_attendee.html", context_dict)

        elif request.method == "POST":
            attendee.surname = request.POST.get("last_name", "")
            attendee.firstname = request.POST.get("first_name", "")
            attendee.patronymic = request.POST.get("patronymic", "")
            attendee.transcription = request.POST.get("latin_name", "")
            attendee.iin = request.POST.get("iin", "")
            attendee.birthDate = request.POST.get("dob", "")
            attendee.sexId = request.POST.get("sex", "")
            attendee.countryId = request.POST.get("citizenship")
            attendee.post = request.POST.get("post", "")
            attendee.docTypeId = request.POST.get("document_type", "")
            attendee.docSeries = request.POST.get("doc_series", "")
            attendee.docNumber = request.POST.get("doc_number", "")
            attendee.docBegin = request.POST.get("doc_date_start", "")
            attendee.docEnd = request.POST.get("doc_date_end", "")
            attendee.docIssue = request.POST.get("doc_issuer", "")
            attendee.visitObjects = request.POST.get("visit_objects", "")
            # Story 3.5: единый residency+ИИН-валидатор (validators/iin.py).
            try:
                dob = datetime.strptime(attendee.birthDate, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                dob = None
            residency = resolve_residency(attendee.countryId, attendee.iin, dob)
            attendee.iin = residency.iin
            attendee.is_resident = residency.is_resident
            # Этап E: пустая или битая дата из прямого POST раньше давала 500 при записи
            # (и стирала файлы участника). Как при добавлении — понятная ошибка формы.
            try:
                for value in (attendee.birthDate, attendee.docBegin, attendee.docEnd):
                    datetime.strptime(value, "%Y-%m-%d")
                dates_ok = True
            except (ValueError, TypeError):
                dates_ok = False

            if not dates_ok:
                context_dict["error_message"] = page_lang.text("bad_date_format", lang)
            elif residency.error:
                iin_error = page_lang.residency_error(residency, lang)
                context_dict["error_message"] = iin_error
                context_dict["iin_error"] = iin_error
            elif upload_error := intake.apply_uploads(attendee, request.FILES, lang, required=False):
                context_dict["error_message"] = upload_error
            elif duplicate := intake.save_unless_duplicate(attendee, req.event_id):
                context_dict["error_message"] = intake.duplicate_text(duplicate, lang)
            else:
                audit_log(
                    user=request.user if request.user.is_authenticated else None,
                    action="attendee.update",
                    obj_type="Attendee",
                    obj_id=attendee_id,
                    ip=request.META.get("REMOTE_ADDR"),
                )

                context_dict["success_message"] = (
                    "Attendee information updated successfully"
                )

            # Story 3.5 review (2026-06-23): сохранить введённые значения при
            # ошибке валидации — иначе date-поля (dob/docBegin/docEnd) обнуляются,
            # т.к. шаблон применяет |date к POST-строке. Паритет с add_attendee.
            context_dict["form_data"] = request.POST
            context_dict.update(_update_attendee_context(attendee, lang))
            context_dict["fv"] = _form_values(post=request.POST)

            if "error_message" in context_dict:
                return render(request, "update_attendee.html", context_dict)

            user = request.user
            if user.is_superuser:
                return redirect("show_event", event_id=req.event_id)
            if user.role == "superoperator" and req.created_by.user_id != user.pk:
                return redirect("superoperator_dashboard", event_id=req.event_id)
            return redirect(page_lang.url(lang, f"/show/{req.pk}/"))
    except Operator.DoesNotExist:
        # P1-1: аутентифицированный пользователь без строки Operator → 403, не 500.
        return HttpResponseForbidden("Operator profile not found.")
    except Attendee.DoesNotExist:
        return HttpResponse("Could not find attendee")
