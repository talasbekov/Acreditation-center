from django.shortcuts import get_object_or_404
from eventproject.operator_activation import send_operator_link
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_http_methods
from pathlib import Path
import re
import logging
import datetime
import mimetypes

from datetime import date, timedelta, datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponse, Http404, HttpResponseRedirect, FileResponse, HttpResponseNotFound
from django.template import RequestContext
from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test

from django.conf import settings
from django.views.decorators.cache import never_cache
from directories.models import Sex, Country, DocumentType, City, Category
from eventproject.view_helpers import get_operator_events, owned_request, owned_requests
from eventproject.models import Event, Operator, Request, Attendee
from eventproject.audit import audit_log
from eventproject.services.access_events import record_access_event
from eventproject.services import lifecycle
from eventproject.services.lifecycle import lifecycle_message
from eventproject import page_lang
from eventproject.views.request import _request_page_context

logger = logging.getLogger("eventproject")


@login_required
def auth_check(request):
    # Это представление всегда возвращает HTTP 200 для авторизованных пользователей,
    # что сигнализирует Nginx о том, что доступ разрешен.
    return HttpResponse()


@never_cache
def protected_media(request, file_path):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    try:
        target = (media_root / file_path).resolve()
        relative = target.relative_to(media_root)
        historical_dir = (media_root / "qr_codes").resolve()
    except (OSError, RuntimeError, ValueError):
        return HttpResponseNotFound()

    # Historical QR files contain the identifier, even under randomized names.
    # Deny before login so a redirect never copies a legacy filename into "next".
    supplied = Path(file_path).parts
    if (
        not relative.parts or not supplied or supplied[0].casefold() == "qr_codes"
        or historical_dir == target or historical_dir in target.parents
    ):
        return HttpResponseNotFound()
    return _serve_authorized_media(request, target, relative.parts[0])


@login_required(login_url="/user_login/")
def _serve_authorized_media(request, target, directory):
    if not request.user.is_superuser:
        event = re.fullmatch(r"event_([0-9]{1,19})", directory)
        if not event or not Operator.objects.filter(
            user=request.user, events__pk=event.group(1),
        ).exists():
            raise Http404

    if not target.is_file():
        raise Http404
    content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    return FileResponse(target.open("rb"), content_type=content_type)


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


def _admin_context(**extra):
    """Главная администратора: мероприятия на 900 дней вперёд, операторы, города.

    P2: пользователь и мероприятия оператора загружаются вместе со списком —
    шаблон обращается к `operator.user` и `operator.events.all` для каждой строки.
    """
    startdate = date.today()
    enddate = startdate + timedelta(days=900)
    context_dict = {
        "events": Event.objects.filter(date_end__range=[startdate, enddate]).order_by("date_start"),
        "operators": Operator.objects.select_related("user")
        .prefetch_related("events")
        .order_by("user__last_name", "user__first_name"),
        "cities": City.objects.all(),
    }
    context_dict.update(extra)
    return context_dict


@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
def index(request):
    return render(request, "index.html", context=_admin_context())


def show_admin(request, success_message):
    return render(request, "index.html", context=_admin_context(success_message=success_message))


def show_admin_error(request, error_message):
    return render(request, "index.html", context=_admin_context(error_message=error_message))


@page_lang.login_required
def application(request, lang="ru"):
    user = request.user
    if user.is_superuser:
        return HttpResponseRedirect("/avmac/")
    try:
        operator = Operator.objects.get(user=user)
    except Operator.DoesNotExist:
        return HttpResponse("You are logged in.")
    startdate = date.today()
    enddate = startdate + timedelta(days=600)
    return render(
        request,
        page_lang.template(lang, "gov2.html"),
        {
            "user": user,
            "operator": operator,
            "events": get_operator_events(user).filter(date_end__range=[startdate, enddate]),
            "reqs": owned_requests(user).order_by("-date_created"),
            "cities": City.objects.all(),
        },
    )

@user_passes_test(lambda u: u.is_superuser, login_url="/user_login/")
@require_POST
@csrf_protect
def new_password(request, username):
    operator = get_object_or_404(Operator.objects.select_related("user"), user__username=username)
    context = {"operator": operator}
    if send_operator_link(operator):
        context["success_message"] = "Ссылка для установки пароля отправлена оператору."
    else:
        context["error_message"] = "Письмо не отправлено. Проверьте активность учётной записи, email оператора и настройки почты."
    start = date.today()
    context["events"] = operator.events.filter(date_end__range=[start, start + timedelta(days=900)]).order_by("-date_start")
    context["reqs"] = Request.objects.filter(created_by=operator).order_by("-date_created")
    return render(request, "operator.html", context)


@page_lang.login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def preview(request, request_id, lang="ru"):
    """Предпросмотр перед отправкой — только чтение: статус заявки не меняется.

    POST принимается для страниц, открытых до обновления (там была форма).
    """
    try:
        req = owned_request(request.user, request_id)
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    if not lifecycle.can_preview(req):
        return HttpResponseRedirect(page_lang.url(lang, f"/show/{req.pk}/"))
    context_dict = _request_page_context(
        req,
        preview=True,
        success_message=page_lang.text("ready_to_send", lang),
        delete_message=page_lang.text("send_warning", lang),
    )
    return render(request, page_lang.template(lang, "request.html"), context_dict)


@page_lang.login_required
@require_POST
@csrf_protect
def back_to_change(request, request_id, lang="ru"):
    """Выход из предпросмотра. Снимает только прежний статус Checking; отправленную заявку не открывает."""
    try:
        req = owned_request(request.user, request_id)
    except Request.DoesNotExist:
        return HttpResponse("Could not find event")
    lifecycle.leave_legacy_preview(req)
    return HttpResponseRedirect(page_lang.url(lang, f"/show/{req.pk}/"))


@page_lang.login_required
@require_POST
@csrf_protect
def send(request, request_id, lang="ru"):
    try:
        req = owned_request(request.user, request_id)
    except (Request.DoesNotExist, Operator.DoesNotExist):
        return HttpResponse("Could not find request")
    extra = {}
    try:
        lifecycle.submit_request(req.pk, request.user, request.META.get("REMOTE_ADDR"))
    except lifecycle.LifecycleError as exc:
        extra["delete_message"] = lifecycle_message(exc, lang)
    req.refresh_from_db()
    if req.status == "Sent":
        extra["success_message"] = page_lang.text("sent_at", lang, time=lifecycle.local_time(req.registration_time))
    return render(request, page_lang.template(lang, "request.html"), _request_page_context(req, **extra))


@page_lang.login_required
def user_logout(request, lang="ru"):
    logout(request)
    return HttpResponseRedirect(page_lang.url(lang, "/user_login/"))


@page_lang.login_required
def change_password(request, lang="ru"):
    context_dict = {}
    result_template = page_lang.template(lang, "change_password_result.html")
    try:
        if request.method == "POST":
            old_password = request.POST["old_password"]
            new_password = request.POST["new_password"]
            new_password_repeat = request.POST["new_password_repeat"]
            if new_password != new_password_repeat:
                context_dict["error_message"] = page_lang.text("pw_mismatch", lang)
                return render(request, result_template, context_dict)
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
                        logger.error("failed to record password_changed event")
                context_dict["success_message"] = page_lang.text("pw_changed", lang)
                return render(request, result_template, context_dict)
            context_dict["error_message"] = page_lang.text("pw_wrong_old", lang)
            return render(request, result_template, context_dict)
    except Exception:
        # L7: не глотаем ошибку молча — логируем и показываем, что смена не удалась.
        logger.error("change_password failed")
        context_dict["error_message"] = page_lang.text("pw_failed", lang)
    return render(request, page_lang.template(lang, "change_password.html"), context_dict)


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


def user_login(request, lang="ru"):
    login_template = page_lang.template(lang, "gov.html")
    if request.method == "POST":
        # P1-2: malformed POST без полей не должен падать KeyError'ом/500.
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        # BE-1: если axes уже заблокировал источник — отдаём локализованное
        # сообщение. Проверяем ДО authenticate: иначе backend выставит
        # request.axes_locked_out и AxesMiddleware подменит ответ на голый
        # англоязычный axes-429 «Account locked…».
        from axes.handlers.proxy import AxesProxyHandler

        if AxesProxyHandler.is_locked(request, {"username": username}):
            return render(
                request, login_template,
                context={"error_message": page_lang.text("login_locked", lang)},
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
                        logger.error("failed to record login access event")
                # P2-9: возврат на исходную страницу (SPA) после входа — только
                # на безопасный (этот хост) next; иначе дефолт по роли.
                next_url = _safe_next_url(request)
                if next_url:
                    return HttpResponseRedirect(next_url)
                if user.is_superuser:
                    return HttpResponseRedirect("/avmac/")
                return HttpResponseRedirect(page_lang.url(lang, "/application/"))
            # Story 2.4 (AC-4): локализованное сообщение о деактивации.
            return render(request, login_template, context={"error_message": page_lang.text("account_disabled", lang)})
        # Story 2.4 (AC-4): дефолтный ModelBackend возвращает None и для
        # неактивных аккаунтов (authenticate проверяет is_active) — поэтому
        # отличаем деактивированный аккаунт от неверных credentials.
        if User.objects.filter(username=username, is_active=False).exists():
            return render(request, login_template, context={"error_message": page_lang.text("account_disabled", lang)})
        return render(
            request,
            login_template,
            context={
                "error_message": page_lang.text("login_bad", lang),
                "next": request.POST.get("next", ""),
            },
        )
    # P2-9: прокидываем next в форму (скрытое поле), чтобы вход вернул на исходную страницу.
    return render(request, login_template, context={"next": request.GET.get("next", "")})


def ratelimited_error(request, exception):
    return HttpResponse("Too many requests. Please try again later.", status=429)
