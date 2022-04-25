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
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = [
    path('create_event/', views.create_event, name='create_event'),
    path('add_operator/', views.add_operator, name='add_operator'),
    path('add_operator_to_event/', views.add_operator_to_event, name='add_operator_to_event'),
    path('user_login/', views.user_login, name='user_login'),
    path('application/', views.application, name='application'),
    path('logout/', views.user_logout, name='logout'),
    path('show_operator/<int:operator_id>/', views.show_operator, name='show_operator'),
    path('create/<int:event_id>/', views.create_request, name='create_request'),
    path('show/<int:request_id>/', views.show_request, name='show_request'),
    path('delete_attendee/', views.delete_attendee, name="delete_attendee"),
    path('add_attendee/<int:request_id>/', views.add_attendee, name='add_attendee'),
    path('delete_request/<int:request_id>/', views.delete_request, name='delete_request'),
    path('preview/<int:request_id>/', views.preview, name='preview'),
    path('back_to_change/<int:request_id>/', views.back_to_change, name='back_to_change'),
    path('send/<int:request_id>/', views.send, name='send'),
    path('change_password/', views.change_password, name='change_password'),
	path('avmac/', views.index, name='index'),
    path('admin/', admin.site.urls),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += staticfiles_urlpatterns()