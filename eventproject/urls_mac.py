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
from django.contrib import admin
from django.urls import path
from eventproject import views
from kz_event import views as kviews
from en_event import views as eviews
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = [
    path("create_event/", views.create_event, name="create_event"),
    path("add_operator/", views.add_operator, name="add_operator"),
    path(
        "add_operator_to_event/",
        views.add_operator_to_event,
        name="add_operator_to_event",
    ),
    path("user_login/", views.user_login, name="user_login"),
    path("application/", views.application, name="application"),
    path("logout/", views.user_logout, name="logout"),
    path("show_operator/<int:operator_id>/", views.show_operator, name="show_operator"),
    path("create/<int:event_id>/", views.create_request, name="create_request"),
    path("show/<int:request_id>/", views.show_request, name="show_request"),
    path("delete_attendee/", views.delete_attendee, name="delete_attendee"),
    path("add_attendee/<int:request_id>/", views.add_attendee, name="add_attendee"),
    path(
        "delete_request/<int:request_id>/", views.delete_request, name="delete_request"
    ),
    path("preview/<int:request_id>/", views.preview, name="preview"),
    path(
        "back_to_change/<int:request_id>/", views.back_to_change, name="back_to_change"
    ),
    path("send/<int:request_id>/", views.send, name="send"),
    path("change_password/", views.change_password, name="change_password"),
    path(
        "show_request_to_admin/<int:request_id>/",
        views.show_request_to_admin,
        name="show_request_to_admin",
    ),
    path("avmac/", views.index, name="index"),
    path(
        "flush_outdated_events/",
        views.flush_outdated_events,
        name="flush_outdated_events",
    ),
    path("new_password/<str:username>/", views.new_password, name="new_password"),
    path(
        "delete_operator/<str:username>/", views.delete_operator, name="delete_operator"
    ),
    path(
        "unbind_event/<int:event_id>/<str:username>/",
        views.unbind_event,
        name="unbind_event",
    ),
    path("show_event/<int:event_id>/", views.show_event, name="show_event"),
    path("delete_event/<int:event_id>/", views.delete_event, name="delete_event"),
    path("download_json/<int:event_id>/", views.download_json, name="download_json"),
    path(
        "download_guests_json/<int:event_id>/",
        views.download_guests_json,
        name="download_json",
    ),
    path(
        "download_photos/<int:event_id>/", views.download_photos, name="download_photos"
    ),
    path("download_file/<int:event_id>/", views.download_file, name="download_file"),
    path("prepare_file/<int:event_id>/", views.prepare_file, name="prepare_file"),
    path(
        "download_request_json/<int:request_id>/",
        views.download_request_json,
        name="download_request_json",
    ),
    path(
        "download_all_guests_json/<int:event_id>/",
        views.download_all_guests_json,
        name="download_all_guests_json",
    ),
    path("", views.user_login, name="user_login"),
    path("kz/", kviews.user_login, name="user_login"),
    path("en/", eviews.user_login, name="user_login"),
    path("kz/user_login/", kviews.user_login, name="user_login"),
    path("en/user_login/", eviews.user_login, name="user_login"),
    path("kz/application/", kviews.application, name="application"),
    path("en/application/", eviews.application, name="application"),
    path("kz/logout/", kviews.user_logout, name="logout"),
    path("en/logout/", eviews.user_logout, name="logout"),
    path("kz/change_password/", kviews.change_password, name="change_password"),
    path("en/change_password/", eviews.change_password, name="change_password"),
    path("kz/create/<int:event_id>/", kviews.create_request, name="create_request"),
    path("en/create/<int:event_id>/", eviews.create_request, name="create_request"),
    path("kz/show/<int:request_id>/", kviews.show_request, name="show_request"),
    path("en/show/<int:request_id>/", eviews.show_request, name="show_request"),
    path("kz/add_attendee/<int:request_id>/", kviews.add_attendee, name="add_attendee"),
    path("en/add_attendee/<int:request_id>/", eviews.add_attendee, name="add_attendee"),
    path(
        "kz/back_to_change/<int:request_id>/",
        kviews.back_to_change,
        name="back_to_change",
    ),
    path(
        "en/back_to_change/<int:request_id>/",
        eviews.back_to_change,
        name="back_to_change",
    ),
    path("kz/preview/<int:request_id>/", kviews.preview, name="preview"),
    path("en/preview/<int:request_id>/", eviews.preview, name="preview"),
    path("kz/send/<int:request_id>/", kviews.send, name="send"),
    path("en/send/<int:request_id>/", eviews.send, name="send"),
    path("kz/delete_attendee/", kviews.delete_attendee, name="delete_attendee"),
    path("en/delete_attendee/", eviews.delete_attendee, name="delete_attendee"),
    path(
        "kz/delete_request/<int:request_id>/",
        kviews.delete_request,
        name="delete_request",
    ),
    path(
        "en/delete_request/<int:request_id>/",
        eviews.delete_request,
        name="delete_request",
    ),
    path("bind_operators/", views.bind_operators, name="bind_operators"),
    path("embankment/", admin.site.urls),
]
# if settings.DEBUG:
#     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# else:
#     urlpatterns += staticfiles_urlpatterns()
