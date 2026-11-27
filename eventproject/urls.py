"""eventproject URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from eventproject.operator_activation import OperatorSetPasswordView
from django.contrib import admin
from django.urls import path, include, re_path
from django.http import JsonResponse

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from eventproject.views import (
    index, application, new_password, send, change_password,
    back_to_change, user_login, preview, user_logout, auth_check,
    protected_media, ratelimited_error, health_check,
    create_event, add_operator_to_event,
    unbind_event, show_event, delete_event,
    download_file, download_json, download_photos, download_guests_json,
    download_request_json, download_all_guests_json,
    show_request_to_admin, show_request, create_request, delete_request,
    add_attendee, update_attendee, delete_attendee,
    add_operator, show_operator, delete_operator, bind_operators,
)
from eventproject.views.dashboard import superoperator_dashboard
from eventproject.views.review import review_decision, review_queue
from eventproject.views.export import (
    export_delta,
    export_package_acknowledge,
    export_package_download,
)
from eventproject.views.file_download import check_archive_status


def health_ok(_request):
    return JsonResponse({"status": "ok"})


def fake_translations(_request):
    return JsonResponse({}, status=200)

urlpatterns = [
    path("api/health/", health_check, name="api_health"),
    path("health/", health_ok, name="health"),
    path("healthz/", health_ok, name="healthz"),
    path('qr/', include('qr_event.urls')),
    path("api/v1/public/content-manager/translations", fake_translations),
    path("api/v1/", include("eventproject.api.urls")),

    path("create_event/", create_event, name="create_event"),
    path("operator-access/<uidb64>/<token>/", OperatorSetPasswordView.as_view(), name="operator-set-password"),
    path("add_operator/", add_operator, name="add_operator"),
    path("add_operator_to_event/", add_operator_to_event, name="add_operator_to_event"),
    path("user_login/", user_login, name="user_login"),
    path("application/", application, name="application"),
    path("logout/", user_logout, name="logout"),
    path("show_operator/<int:operator_id>/", show_operator, name="show_operator"),
    path("create/<int:event_id>/", create_request, name="create_request"),
    path("show/<int:request_id>/", show_request, name="show_request"),
    path("delete_attendee/", delete_attendee, name="delete_attendee"),
    path("add_attendee/<int:request_id>/", add_attendee, name="add_attendee"),
    path(
        "update_attendee/<int:attendee_id>/",
        update_attendee,
        name="update_attendee",
    ),
    path("delete_request/<int:request_id>/", delete_request, name="delete_request"),
    path("preview/<int:request_id>/", preview, name="preview"),
    path("back_to_change/<int:request_id>/", back_to_change, name="back_to_change"),
    path("send/<int:request_id>/", send, name="send"),
    path("change_password/", change_password, name="change_password"),
    path(
        "show_request_to_admin/<int:request_id>/",
        show_request_to_admin,
        name="show_request_to_admin",
    ),
    path("avmac/", index, name="index"),
    path("new_password/<str:username>/", new_password, name="new_password"),
    path("delete_operator/<str:username>/", delete_operator, name="delete_operator"),
    path(
        "unbind_event/<int:event_id>/<str:username>/", unbind_event, name="unbind_event"
    ),
    path("show_event/<int:event_id>/", show_event, name="show_event"),
    path("dashboard/<int:event_id>/", superoperator_dashboard, name="superoperator_dashboard"),
    path("review/<int:event_id>/", review_queue, name="review_queue"),
    path(
        "review/attendee/<int:attendee_id>/<str:decision>/",
        review_decision,
        name="review_decision",
    ),
    path("export_delta/<int:event_id>/<int:request_id>/", export_delta, name="export_delta"),
    path(
        "export_package/<uuid:package_id>/download/",
        export_package_download,
        name="export_package_download",
    ),
    path(
        "export_package/<uuid:package_id>/acknowledge/",
        export_package_acknowledge,
        name="export_package_acknowledge",
    ),
    path("delete_event/<int:event_id>/", delete_event, name="delete_event"),
    path("download_json/<int:event_id>/", download_json, name="download_json"),
    path(
        "download_guests_json/<int:event_id>/",
        download_guests_json,
        name="download_guests_json",
    ),
    path("download_photos/<int:event_id>/", download_photos, name="download_photos"),
    path("download_file/<int:event_id>/", download_file, name="download_file"),
    path('check_archive_status/<int:event_id>/', check_archive_status, name='check_archive_status'),
    # path('archive/<int:event_id>/', EventArchiveView.as_view(), name='event_archive'),
    # path('prepare_file/<int:event_id>/', prepare_file, name='prepare_file'),
    path(
        "download_request_json/<int:request_id>/",
        download_request_json,
        name="download_request_json",
    ),
    path(
        "download_all_guests_json/<int:event_id>/",
        download_all_guests_json,
        name="download_all_guests_json",
    ),
    path("auth_check/", auth_check, name="auth_check"),
    # Локализованные (RU/KZ/EN) маршруты. Каждое имя уникально, иначе `reverse()`/
    # `{% url %}` молча резолвят дубль non-namespaced имени в ПОСЛЕДНИЙ паттерн (en/…),
    # уводя пользователей дефолтной (RU) локали на англоязычные хендлеры. RU — канонические
    # bare-имена (выше), KZ/EN — с префиксом kz_/en_.
    path("", user_login, name="user_login_root"),
    path("kz/", user_login, {"lang": "kz"}, name="kz_user_login_root"),
    path("en/", user_login, {"lang": "en"}, name="en_user_login_root"),
    path("kz/user_login/", user_login, {"lang": "kz"}, name="kz_user_login"),
    path("en/user_login/", user_login, {"lang": "en"}, name="en_user_login"),
    path("kz/application/", application, {"lang": "kz"}, name="kz_application"),
    path("en/application/", application, {"lang": "en"}, name="en_application"),
    path("kz/logout/", user_logout, {"lang": "kz"}, name="kz_logout"),
    path("en/logout/", user_logout, {"lang": "en"}, name="en_logout"),
    path("kz/change_password/", change_password, {"lang": "kz"}, name="kz_change_password"),
    path("en/change_password/", change_password, {"lang": "en"}, name="en_change_password"),
    path("kz/create/<int:event_id>/", create_request, {"lang": "kz"}, name="kz_create_request"),
    path("en/create/<int:event_id>/", create_request, {"lang": "en"}, name="en_create_request"),
    path("kz/show/<int:request_id>/", show_request, {"lang": "kz"}, name="kz_show_request"),
    path("en/show/<int:request_id>/", show_request, {"lang": "en"}, name="en_show_request"),
    path("kz/add_attendee/<int:request_id>/", add_attendee, {"lang": "kz"}, name="kz_add_attendee"),
    path("en/add_attendee/<int:request_id>/", add_attendee, {"lang": "en"}, name="en_add_attendee"),
    path(
        "kz/back_to_change/<int:request_id>/",
        back_to_change, {"lang": "kz"},
        name="kz_back_to_change",
    ),
    path(
        "en/back_to_change/<int:request_id>/",
        back_to_change, {"lang": "en"},
        name="en_back_to_change",
    ),
    path("kz/preview/<int:request_id>/", preview, {"lang": "kz"}, name="kz_preview"),
    path("en/preview/<int:request_id>/", preview, {"lang": "en"}, name="en_preview"),
    path("kz/send/<int:request_id>/", send, {"lang": "kz"}, name="kz_send"),
    path("en/send/<int:request_id>/", send, {"lang": "en"}, name="en_send"),
    path("kz/delete_attendee/", delete_attendee, {"lang": "kz"}, name="kz_delete_attendee"),
    path("kz/update_attendee/<int:attendee_id>/", update_attendee, {"lang": "kz"}, name="kz_update_attendee"),
    path("en/update_attendee/<int:attendee_id>/", update_attendee, {"lang": "en"}, name="en_update_attendee"),
    path("en/delete_attendee/", delete_attendee, {"lang": "en"}, name="en_delete_attendee"),
    path(
        "kz/delete_request/<int:request_id>/",
        delete_request, {"lang": "kz"},
        name="kz_delete_request",
    ),
    path(
        "en/delete_request/<int:request_id>/",
        delete_request, {"lang": "en"},
        name="en_delete_request",
    ),
    path("bind_operators/", bind_operators, name="bind_operators"),
    path("embankment/", admin.site.urls),
    # PII-медиа (фото, сканы паспортов) — только через protected_media:
    # login + проверка, что оператор привязан к событию (event_<id>/...).
    re_path(r"^media/(?P<file_path>.+)$", protected_media, name="media"),
]

if settings.DEBUG:
    # ВНИМАНИЕ: /media/ НЕ раздаётся через static() — это PII. Весь доступ идёт
    # через protected_media (выше). Здесь только статика приложения (css/js).
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += [path("graphql", lambda r: JsonResponse({"detail": "GraphQL not enabled"}, status=404))]

# handler404 = 'eventproject.views.views.custom_page_not_found'
handler429 = 'eventproject.views.ratelimited_error'
