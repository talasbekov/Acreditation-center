import os
import re
import logging
import datetime
import secrets
import mimetypes

from datetime import date, timedelta, datetime
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponse, Http404, HttpResponseRedirect, FileResponse, HttpResponseNotFound
from django.template import RequestContext
from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test

from django.conf import settings
from directories.models import Sex, Country, DocumentType, City
from eventproject.models import Event, Operator, Request, Attendee
from eventproject.audit import audit_log
from eventproject.services.access_events import record_access_event

logger = logging.getLogger("eventproject")


@login_required
def auth_check(request):
    # Это представление всегда возвращает HTTP 200 для авторизованных пользователей,
    # что сигнализирует Nginx о том, что доступ разрешен.
    return HttpResponse()


@login_required(login_url="/user_login/")
def protected_media(request, file_path):
    # Защита от path traversal: путь после realpath обязан остаться внутри MEDIA_ROOT
    media_root = os.path.realpath(settings.MEDIA_ROOT)
    full_path = os.path.realpath(os.path.join(media_root, file_path))
    if os.path.commonpath([full_path, media_root]) != media_root:
        raise Http404

    # Авторизация на уровне объекта: оператор получает файлы только своих событий.
    # Медиа лежит в каталогах вида event_<id>/...  Суперпользователь — без ограничений.
    # 404 (а не 403), чтобы не раскрывать существование чужих файлов.
    if not request.user.is_superuser:
        match = re.match(r"event_(\d+)/", file_path)
        if not match:
            raise Http404
        try:
            operator = Operator.objects.get(user=request.user)
        except Operator.DoesNotExist:
            raise Http404
        if not operator.events.filter(pk=int(match.group(1))).exists():
            raise Http404

    if not os.path.isfile(full_path):
        raise Http404

    content_type, _ = mimetypes.guess_type(full_path)
    if content_type is None:
        content_type = "application/octet-stream"

    # Файл закрывается самим FileResponse после стриминга — не использовать with
    return FileResponse(open(full_path, "rb"), content_type=content_type)

# from django.shortcuts import redirect
# from django.http import HttpResponseNotFound
# from django.urls import get_resolver, Resolver404
#
# def custom_page_not_found(request, exception=None):
#     # Берем только первый сегмент URL после слэша
#     first_segment = request.path_info.strip("/").split("/")[0]
#
#     try:
#         # Пробуем найти совпадение хотя бы по первому сегменту
#         get_resolver().resolve(f"/{first_segment}/")
#         # Если сегмент существует, но URL не совпал полностью → обычная 404
#         return HttpResponseNotFound("Page not found")
#     except Resolver404:
#         # Если даже первый сегмент не существует → редирект на главную
#         return redirect('/')


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def index(request):
    # Construct a dictionary to pass to the template engine as its context.
    # Note the key boldmessage is the same as {{ boldmessage }} in the template!
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    event_list = Event.objects.filter(date_end__range=[startdate, enddate]).order_by(
        "date_start"
    )
    operators = Operator.objects.all().order_by("user__last_name", "user__first_name")
    cities = City.objects.all()
    context_dict = {"events": event_list}
    context_dict["operators"] = operators
    context_dict["cities"] = cities
    return render(request, "index.html", context=context_dict)


def show_admin(request, success_message):
    # Construct a dictionary to pass to the template engine as its context.
    # Note the key boldmessage is the same as {{ boldmessage }} in the template!
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    event_list = Event.objects.filter(date_end__range=[startdate, enddate]).order_by(
        "date_start"
    )
    operators = Operator.objects.all()
    cities = City.objects.all()
    context_dict = {"events": event_list}
    context_dict["operators"] = operators
    context_dict["success_message"] = success_message
    context_dict["cities"] = cities
    return render(request, "index.html", context=context_dict)


def show_admin_error(request, error_message):
    # Construct a dictionary to pass to the template engine as its context.
    # Note the key boldmessage is the same as {{ boldmessage }} in the template!
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    event_list = Event.objects.filter(date_end__range=[startdate, enddate]).order_by(
        "date_start"
    )
    operators = Operator.objects.all()
    cities = City.objects.all()
    context_dict = {"events": event_list}
    context_dict["operators"] = operators
    context_dict["error_message"] = error_message
    context_dict["cities"] = cities
    return render(request, "index.html", context=context_dict)


@login_required(login_url="/user_login/")
def application(request):
    if not request.user.is_authenticated:
        return HttpResponse("You are logged in.")
    user = request.user
    if user.is_superuser:
        return HttpResponseRedirect("/avmac/")
    try:
        operator = Operator.objects.get(user=user)
    except Operator.DoesNotExist:
        return HttpResponse("You are logged in.")
    cities = City.objects.all()
    startdate = date.today()
    enddate = startdate + timedelta(days=600)
    events = operator.events.filter(date_end__range=[startdate, enddate])
    reqs = Request.objects.filter(created_by=operator).order_by("-date_created")
    return render(
        request,
        "gov2.html",
        {
            "user": user,
            "operator": operator,
            "events": events,
            "reqs": reqs,
            "cities": cities,
        },
    )


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
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
        event_list = operator.events.filter(
            date_end__range=[startdate, enddate]
        ).order_by("-date_start")
        reqs = Request.objects.filter(created_by=operator).order_by("-date_created")
        context_dict["events"] = event_list
        context_dict["operator"] = operator
        context_dict["requests"] = reqs
        context_dict["success_message"] = "Сгенерирован новый пароль: " + password
    except (User.DoesNotExist, Operator.DoesNotExist):
        return HttpResponse("Could not find operator")
    return render(request, "operator.html", context_dict)


@login_required(login_url="/user_login/")
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
        context_dict["success_message"] = "Заявка готова к отправлению"
        context_dict[
            "delete_message"
        ] = "Внимание!!! Отправка заявки не гарантирует допуск участника в зону проведения охранного мероприятия в установленную дату"
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    return render(request, "request.html", context_dict)


@login_required(login_url="/user_login/")
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
    return render(request, "request.html", context_dict)


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
        req.registration_time = timezone.now()
        req.save()
        attendees = Attendee.objects.filter(request=req)
        context_dict["attendees"] = attendees
        countries = Country.objects.all()
        context_dict["countries"] = countries
        document_types = DocumentType.objects.all()
        context_dict["document_types"] = document_types
        sexs = Sex.objects.all()
        context_dict["sexs"] = sexs
        context_dict["success_message"] = "Отправлено " + str(req.registration_time)
    except (Request.DoesNotExist, Operator.DoesNotExist):
        return HttpResponse("Could not find request")
    return render(request, "request.html", context_dict)


@login_required(login_url="/user_login/")
def user_logout(request):
    logout(request)
    return HttpResponseRedirect("/user_login/")


@login_required(login_url="/user_login/")
def change_password(request):
    context_dict = {}
    try:
        if request.method == "POST":
            old_password = request.POST["old_password"]
            new_password = request.POST["new_password"]
            new_password_repeat = request.POST["new_password_repeat"]
            if new_password != new_password_repeat:
                context_dict["error_message"] = "Введите новый пароль два раза"
                return render(request, "change_password_result.html", context_dict)
            if request.user.check_password(old_password):
                request.user.set_password(new_password)
                request.user.save()
                # Сохраняем сессию активной после смены пароля (иначе Django
                # ротирует auth-hash и пользователь разлогинивается).
                update_session_auth_hash(request, request.user)
                # Story 2.3 (AC-5): снимаем форс смены пароля после успешной смены.
                operator = getattr(request.user, "operator", None)
                if operator is not None and operator.force_password_change:
                    operator.force_password_change = False
                    operator.save(update_fields=["force_password_change"])
                # Story 2.4 (AC-3): фиксируем смену пароля в истории доступа + audit.
                # Best-effort: пароль уже изменён — сбой записи истории не должен
                # привести к ложному «не удалось изменить пароль».
                if operator is not None:
                    try:
                        ip = request.META.get("REMOTE_ADDR", "")
                        record_access_event(
                            operator, "password_changed", actor=request.user, ip=ip
                        )
                        audit_log(
                            user=request.user,
                            action="user.change_password",
                            obj_type="User",
                            obj_id=request.user.id,
                            ip=ip,
                        )
                    except Exception:
                        logger.exception(
                            "failed to record password_changed event for user=%s",
                            request.user.id,
                        )
                context_dict["success_message"] = "Пароль успешно изменен"
                return render(request, "change_password_result.html", context_dict)
            else:
                context_dict["error_message"] = "Не удалось подтвердить данные"
                return render(request, "change_password_result.html", context_dict)
    except Exception as e:
        # L7: не глотаем ошибку молча (был print("unknown")) — логируем и
        # показываем пользователю, что смена пароля не удалась.
        logger.error(
            "change_password failed for user=%s: %s",
            getattr(request.user, "id", None), e,
        )
        context_dict["error_message"] = "Не удалось изменить пароль. Попробуйте ещё раз."
    return render(request, "change_password.html", context_dict)


def _safe_next_url(request):
    """P2-9: возвращает ?next= только если он указывает на ЭТОТ хост (анти open-redirect).

    Внешний/протокол-относительный (`//evil`) URL → None (используется дефолтный редирект).
    """
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(
        nxt,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return nxt
    return None


def user_login(request):
    context = RequestContext(request)
    if request.method == "POST":
        # P1-2: malformed POST без полей не должен падать KeyError'ом/500.
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        # BE-1: если axes уже заблокировал источник — отдаём локализованное
        # сообщение. Проверяем ДО authenticate: иначе backend выставит
        # request.axes_locked_out и AxesMiddleware подменит ответ на голый
        # англоязычный axes-429 «Account locked…».
        from axes.handlers.proxy import AxesProxyHandler

        if AxesProxyHandler.is_locked(request, {"username": username}):
            return render(
                request,
                "gov.html",
                context={
                    "error_message": (
                        "Аккаунт временно заблокирован из-за множества неудачных "
                        "попыток входа. Повторите попытку позже."
                    ),
                },
                status=429,
            )
        user = authenticate(request, username=username, password=password)
        if user is not None:

            if user.is_active:
                login(request, user)
                # Story 2.4 (AC-3): фиксируем вход оператора в истории доступа + audit.
                # Best-effort: сбой записи истории НЕ должен ломать уже успешный вход.
                operator = getattr(user, "operator", None)
                if operator is not None:
                    try:
                        ip = request.META.get("REMOTE_ADDR", "")
                        record_access_event(operator, "login", actor=user, ip=ip)
                        audit_log(
                            user=user,
                            action="user.login",
                            obj_type="User",
                            obj_id=user.id,
                            ip=ip,
                        )
                    except Exception:
                        logger.exception(
                            "failed to record login access event for user=%s", user.id
                        )
                # P2-9: возврат на исходную страницу (SPA) после входа — только
                # на безопасный (этот хост) next; иначе дефолт по роли.
                next_url = _safe_next_url(request)
                if next_url:
                    return HttpResponseRedirect(next_url)
                if user.is_superuser:
                    return HttpResponseRedirect("/avmac/")
                else:
                    return HttpResponseRedirect("/application/")
            else:
                # Story 2.4 (AC-4): локализованное сообщение о деактивации.
                return render(
                    request,
                    "gov.html",
                    context={"error_message": "Аккаунт деактивирован"},
                )
        else:
            # Story 2.4 (AC-4): дефолтный ModelBackend возвращает None и для
            # неактивных аккаунтов (authenticate проверяет is_active) — поэтому
            # отличаем деактивированный аккаунт от неверных credentials.
            if User.objects.filter(username=username, is_active=False).exists():
                return render(
                    request,
                    "gov.html",
                    context={"error_message": "Аккаунт деактивирован"},
                )
            return render(
                request,
                "gov.html",
                context={
                    "error_message": "Неправильный логин или пароль",
                    "next": request.POST.get("next", ""),
                },
            )
    # P2-9: прокидываем next в форму (скрытое поле), чтобы вход вернул на исходную страницу.
    return render(request, "gov.html", context={"next": request.GET.get("next", "")})


def ratelimited_error(request, exception):
    return HttpResponse("Too many requests. Please try again later.", status=429)
