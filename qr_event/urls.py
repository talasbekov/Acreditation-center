# qr_event/urls.py
from django.urls import path
from .views import iin_view, qr_success_view

urlpatterns = [
    path('', iin_view, name='iin_form'),
    path('success/<int:pk>/', qr_success_view, name='qr_success'),
]
