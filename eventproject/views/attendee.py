
import logging
from datetime import date, datetime

from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django_ratelimit.decorators import ratelimit

from directories.models import Sex, Country, DocumentType, Category
from eventproject.models import Operator, Request, Attendee
from eventproject.validators.iin import event_has_iin_duplicate
from eventproject.validators.residency import resolve_residency
from eventproject.audit import audit_log

logger = logging.getLogger("eventproject")


def _ratelimit_response():
    return HttpResponse("Too many requests. Please try again later.", status=429)


def _update_attendee_context(attendee):
    return {
        "attendee": attendee,
        "countries": sorted(Country.objects.all(), key=lambda x: x.name_rus),
        "document_types": DocumentType.objects.all(),
        "sexs": Sex.objects.all(),
        "categories": Category.objects.all(),
    }


def _csrf_missing(request):
    return request.method == "POST" and not (
        request.POST.get("csrfmiddlewaretoken")
        or request.META.get("HTTP_X_CSRFTOKEN")
    )


@login_required(login_url="/user_login/")
def delete_attendee(request):
    context_dict = {}
    try:
        if request.method == "POST":
            attendee_id = request.POST.get("attendee_id")
            if not attendee_id:
                return HttpResponse("No attendee ID provided", status=400)

            # Проверяем, существует ли участник
            attendee = get_object_or_404(Attendee, id=attendee_id)
            req = attendee.request
            user = request.user

            # Проверка прав доступа для обычного пользователя (не суперпользователя)
            if not user.is_superuser:
                try:
                    operator = Operator.objects.get(user=user)
                except Operator.DoesNotExist:
                    return HttpResponse("Operator not found", status=403)

                if req.created_by != operator:
                    return HttpResponse(
                        "You are not authorised to see this page", status=403
                    )

            if not user.is_superuser and req.created_by != operator:
                return HttpResponse(
                    "You are not authorised to see this page", status=403
                )

            # Удаляем участника
            attendee.delete()

            audit_log(
                user=request.user if request.user.is_authenticated else None,
                action="attendee.delete",
                obj_type="Attendee",
                obj_id=attendee_id,
                ip=request.META.get("REMOTE_ADDR"),
            )

            # Проверяем, сколько участников осталось для данного запроса
            remaining_attendees = Attendee.objects.filter(request=req)
            if not remaining_attendees:
                # Если участников больше нет, удаляем запрос
                req.delete()
                context_dict["delete_message"] = (
                    f"Запрос {req.id} был удален, так как не осталось участников"
                )
            else:
                context_dict["delete_message"] = (
                    f"Участник {attendee.surname} {attendee.firstname} был успешно удален"
                )

            # Подготовка данных для отображения
            context_dict["req"] = req
            context_dict["attendees"] = remaining_attendees
            context_dict["countries"] = Country.objects.all()
            context_dict["document_types"] = DocumentType.objects.all()
            context_dict["sexs"] = Sex.objects.all()

    except Attendee.DoesNotExist:
        return HttpResponse("Attendee not found", status=404)
    except Exception as e:
        logger.exception("delete_attendee failed: %s", e)
        return HttpResponse("Не удалось удалить участника", status=500)

    if user.is_superuser:
        return render(request, "request_admin.html", context_dict)
    else:
        return render(request, "request.html", context_dict)


def check_dublicate(attendee, req):
    attendees = Attendee.objects.filter(request__event=req.event)
    if attendee.countryId == "1000000105":
        return event_has_iin_duplicate(attendees, attendee.iin, exclude_pk=attendee.pk)
    else:
        fa = attendees.filter(
            surname=attendee.surname,
            firstname=attendee.firstname,
            birthDate=attendee.birthDate,
        )
    return fa.exists()


@ratelimit(key="ip", rate="20/h", method="POST", block=False)
@csrf_protect
@login_required(login_url="/user_login/")
def add_attendee(request, request_id):
    context_dict = {}
    if getattr(request, "limited", False):
        return _ratelimit_response()
    if _csrf_missing(request):
        return HttpResponseForbidden("CSRF verification failed. Request aborted.")
    countries = Country.objects.all()
    context_dict["countries"] = countries.order_by("name_rus")
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
        user = request.user
        if not user.is_superuser:
            operator = Operator.objects.get(user=request.user)
            if req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")
        attendee = Attendee()
        attendee.surname = request.POST["last_name"]
        attendee.firstname = request.POST["first_name"]
        attendee.patronymic = request.POST["patronymic"]
        attendee.transcription = request.POST["latin_name"]
        attendee.iin = request.POST.get("iin", "")
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
        attendee.dateAdd = timezone.now()
        attendee.dateEnd = date.today()
        if attendee.countryId != "1000000105aaaa":
            attendee.stickId = request.POST["category"]
        doc_start = datetime.strptime(attendee.docBegin, "%Y-%m-%d").date()
        doc_end = datetime.strptime(attendee.docEnd, "%Y-%m-%d").date()
        dob = datetime.strptime(attendee.birthDate, "%Y-%m-%d").date()
        # Story 3.5: единый residency+ИИН-валидатор (validators/iin.py).
        residency = resolve_residency(attendee.countryId, attendee.iin, dob)
        attendee.iin = residency.iin
        attendee.is_resident = residency.is_resident
        if doc_start > date.today():
            context_dict["delete_message"] = (
                "Не удалось добавить. Дата выдачи документа еще не наступил"
            )
        elif doc_end < date.today():
            context_dict["delete_message"] = "Не удалось добавить. Истек срок документа"
        elif dob > date.today():
            context_dict["delete_message"] = (
                "Не удалось добавить. Проверьте дату рождения"
            )
        elif attendee.photo.size > 9000000:
            context_dict["delete_message"] = (
                "Не удалось добавить. Размер фотографии превышает 7Mb"
            )
        elif attendee.photo.size < 1000:
            context_dict["delete_message"] = (
                "Не удалось добавить. Размер фотографии меньше чем 1Kb"
            )
        elif attendee.docScan.size > 9000000:
            context_dict["delete_message"] = (
                "Не удалось добавить. Размер скана документа превышает 7Mb"
            )
        elif attendee.docScan.size < 1000:
            context_dict["delete_message"] = (
                "Не удалось добавить. Размер скана документа меньше чем 1Kb"
            )
        elif residency.error:
            context_dict["delete_message"] = "Не удалось добавить. " + residency.error
            context_dict["iin_error"] = residency.error
        elif check_dublicate(attendee, req):
            context_dict["delete_message"] = (
                "Не удалось добавить. Уже ранее добавляли этого участника"
            )
        else:
            attendee.save()

            audit_log(
                user=request.user if request.user.is_authenticated else None,
                action="attendee.create",
                obj_type="Attendee",
                obj_id=attendee.id,
                ip=request.META.get("REMOTE_ADDR"),
            )

            context_dict["success_message"] = (
                "Участник "
                + attendee.surname
                + " "
                + attendee.firstname
                + " был успешно добавлен"
            )
        context_dict["req"] = req
        attendees = Attendee.objects.filter(request=req).order_by("-dateAdd")
        context_dict["attendees"] = attendees
        # Story 3.5 (AC-2): сохранить введённые данные при ошибке.
        context_dict["form_data"] = request.POST
        if "delete_message" in context_dict:
            return render(request, "gov3.html", context_dict)
        else:
            return render(request, "request.html", context_dict)
    # except Exception as e:
    #    return HttpResponse("Could not add a guest")
    return render(request, "gov3.html", context_dict)


@ratelimit(key="ip", rate="20/h", method="POST", block=False)
@csrf_protect
@login_required(login_url="/user_login/")
def update_attendee(request, attendee_id):
    context_dict = {}
    if getattr(request, "limited", False):
        return _ratelimit_response()
    if _csrf_missing(request):
        return HttpResponseForbidden("CSRF verification failed. Request aborted.")
    try:
        attendee = Attendee.objects.get(id=attendee_id)
        req = attendee.request
        user = request.user
        if not user.is_superuser:
            operator = Operator.objects.get(user=request.user)
            # Story 4.2 (review, AC-3): Супероператор (по роли) редактирует любого
            # участника — дашборд статусов ссылается сюда. Обычный оператор — только
            # заявки, которые сам создал.
            is_superoperator = operator.role in ("superoperator", "superuser")
            if not is_superoperator and req.created_by != operator:
                return HttpResponse("You are not authorised to see this page")

        if request.method == "GET":
            context_dict.update(_update_attendee_context(attendee))
            return render(request, "update_attendee.html", context_dict)

        elif request.method == "POST":
            attendee.surname = request.POST["last_name"]
            attendee.firstname = request.POST["first_name"]
            attendee.patronymic = request.POST["patronymic"]
            attendee.transcription = request.POST["latin_name"]
            attendee.iin = request.POST.get("iin", "")
            attendee.birthDate = request.POST["dob"]
            attendee.sexId = request.POST["sex"]
            attendee.countryId = request.POST.get("citizenship")
            attendee.post = request.POST["post"]
            attendee.docTypeId = request.POST["document_type"]
            attendee.docSeries = request.POST["doc_series"]
            attendee.docNumber = request.POST["doc_number"]
            attendee.docBegin = request.POST["doc_date_start"]
            attendee.docEnd = request.POST["doc_date_end"]
            attendee.docIssue = request.POST["doc_issuer"]
            attendee.visitObjects = request.POST["visit_objects"]
            uploaded_photo = request.FILES.get("photo")
            uploaded_doc_scan = request.FILES.get("doc_photo")

            if uploaded_photo is not None:
                attendee.photo = uploaded_photo
            if uploaded_doc_scan is not None:
                attendee.docScan = uploaded_doc_scan

            # Story 3.5: единый residency+ИИН-валидатор (validators/iin.py).
            try:
                dob = datetime.strptime(attendee.birthDate, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                dob = None
            residency = resolve_residency(attendee.countryId, attendee.iin, dob)
            attendee.iin = residency.iin
            attendee.is_resident = residency.is_resident

            if uploaded_photo is not None and attendee.photo.size > 9000000:
                context_dict["error_message"] = "Photo size exceeds the limit (9MB)"
            elif uploaded_doc_scan is not None and attendee.docScan.size > 9000000:
                context_dict["error_message"] = (
                    "Document scan size exceeds the limit (9MB)"
                )
            elif residency.error:
                context_dict["error_message"] = residency.error
                context_dict["iin_error"] = residency.error
            else:
                attendee.save()

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
            context_dict.update(_update_attendee_context(attendee))

            if "error_message" in context_dict:
                return render(request, "update_attendee.html", context_dict)

            user = request.user
            if user.is_superuser:
                return redirect(f"/show_event/{req.event.id}/")
            else:
                return redirect(f"/show/{req.id}/")
    except Attendee.DoesNotExist:
        return HttpResponse("Could not find attendee")
