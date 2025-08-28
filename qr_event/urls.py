# qr_event/urls.py
from django.urls import path
from .views import iin_view

urlpatterns = [
    path('', iin_view, name='iin_form'),
]
