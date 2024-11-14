import datetime
from datetime import date

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from directories.models import Sex, Country, DocumentType, Category
from eventproject.models import Operator, Request, Attendee


@login_required(login_url="/user_login/")
def delete_attendee(request):
    context_dict = {}
    try:
        if request.method == "POST":
            attendee_id = request.POST["attendee_id"]
            attendee = Attendee.objects.get(id=attendee_id)
            req = attendee.request
            user = request.user
            operator = Operator.objects.get(user=request.user)
            if req.event not in operator.events.all():
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
                "Участник "
                + attendee.surname
                + " "
                + attendee.firstname
                + " был успешно удален"
            )
            attendee.delete()
            # Проверяем, сколько осталось участников для данного запроса
            remaining_attendees = Attendee.objects.filter(request=req)

            if not remaining_attendees:
                # Если участников больше нет, удаляем запрос
                req.delete()
    except Attendee.DoesNotExist:
        return HttpResponse("Could not find event")
    if user.is_superuser:
        return render(request, "request_admin.html", context_dict)
    else:
        return render(request, "request.html", context_dict)


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


@login_required(login_url="/user_login/")
def add_attendee(request, request_id):
    context_dict = {}
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

        photo_file = request.FILES.get("photo")
        if photo_file:
            allowed_extensions = {".jpg", ".jpeg", ".png"}
            file_extension = photo_file.name.split(".")[-1].lower()
            if file_extension not in allowed_extensions:
                context_dict["delete_message"] = (
                    "Загрузите файл с форматом фотографии .jpg, .jpeg, .png"
                )
                return render(request, "gov3.html", context_dict)

        if attendee.countryId != "1000000105aaaa":
            attendee.stickId = request.POST["category"]
        doc_start = datetime.strptime(attendee.docBegin, "%Y-%m-%d").date()
        doc_end = datetime.strptime(attendee.docEnd, "%Y-%m-%d").date()
        dob = datetime.strptime(attendee.birthDate, "%Y-%m-%d").date()
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
        elif attendee.photo.size < 50000:
            context_dict["delete_message"] = (
                "Не удалось добавить. Размер фотографии меньше чем 50Kb"
            )
        elif attendee.docScan.size > 9000000:
            context_dict["delete_message"] = (
                "Не удалось добавить. Размер скана документа превышает 7Mb"
            )
        elif attendee.docScan.size < 50000:
            context_dict["delete_message"] = (
                "Не удалось добавить. Размер скана документа меньше чем 50Kb"
            )
        elif attendee.countryId == "1000000105" and len(attendee.iin) < 12:
            context_dict["delete_message"] = (
                "Не удалось добавить. ИИН обязателен для граждан Казахстана"
            )
        elif check_dublicate(attendee, req):
            context_dict["delete_message"] = (
                "Не удалось добавить. Уже ранее добавляли этого участника"
            )
        else:
            attendee.save()
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
        if "delete_message" in context_dict:
            return render(request, "gov3.html", context_dict)
        else:
            return render(request, "request.html", context_dict)
        # except Exception as e:
        #    return HttpResponse("Could not add a guest")
    return render(request, "gov3.html", context_dict)


@login_required(login_url="/user_login/")
def update_attendee(request, attendee_id):
    context_dict = {}
    try:
        attendee = Attendee.objects.get(id=attendee_id)
        req = attendee.request
        operator = Operator.objects.get(user=request.user)

        if req.event not in operator.events.all():
            return HttpResponse("You are not authorized to update this attendee")

        if request.method == "GET":
            # Отобразите форму для обновления данных участника, заполнив текущими данными
            context_dict["attendee"] = attendee
            countries = Country.objects.all()
            context_dict["countries"] = countries
            document_types = DocumentType.objects.all()
            context_dict["document_types"] = document_types
            sexs = Sex.objects.all()
            context_dict["sexs"] = sexs
            categories = Category.objects.all()
            context_dict["categories"] = categories
            return render(request, "update_attendee.html", context_dict)

        elif request.method == "POST":
            # Получите обновленные данные из формы и обновите запись участника
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
            attendee.docScan = request.FILES["doc_photo"]
            attendee.visitObjects = request.POST["visit_objects"]

            photo_file = request.FILES.get("photo")
            if photo_file:
                allowed_extensions = {".jpg", ".jpeg", ".png"}
                file_extension = photo_file.name.split(".")[-1].lower()
                if file_extension not in allowed_extensions:
                    context_dict["delete_message"] = (
                        "Загрузите файл с форматом фотографии .jpg, .jpeg, .png"
                    )
                    return render(request, "gov3.html", context_dict)

            # Проверьте данные на валидность и соответствие ограничениям (например, размер фотографии)
            if attendee.photo.size > 9000000:
                context_dict["error_message"] = "Photo size exceeds the limit (9MB)"
            elif attendee.docScan.size > 9000000:
                context_dict["error_message"] = (
                    "Document scan size exceeds the limit (9MB)"
                )
            else:
                # Сохраните обновленные данные и вернитесь к странице участника
                attendee.save()
                context_dict["success_message"] = (
                    "Attendee information updated successfully"
                )

            context_dict["attendee"] = attendee
            countries = Country.objects.all()
            context_dict["countries"] = countries
            document_types = DocumentType.objects.all()
            context_dict["document_types"] = document_types
            sexs = Sex.objects.all()
            context_dict["sexs"] = sexs
            categories = Category.objects.all()
            context_dict["categories"] = categories

            user = request.user
            if user.is_superuser:
                return redirect(f"/show_event/{req.event.id}/")
            else:
                return redirect(f"/show/{req.id}/")
    except Attendee.DoesNotExist:
        return HttpResponse("Could not find attendee")
