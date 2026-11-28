from django.http import JsonResponse
from django.urls import path
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from eventproject.views.event import EventViewSet
from eventproject.views.operator_api import OperatorViewSet
from eventproject.views.attendee_api import AttendeeViewSet
from eventproject.views.request_api import RequestViewSet
from eventproject.views.directories_api import directories
from eventproject.views.auth_api import ChangePasswordView, LoginView, LogoutView, MeView


@ensure_csrf_cookie
def csrf_cookie(request):
    """P2-8: ставит `csrftoken` cookie до первой мутации из SPA (без auth)."""
    return JsonResponse({"detail": "CSRF cookie set"})


router = DefaultRouter()
router.register(r"events", EventViewSet, basename="event")
router.register(r"operators", OperatorViewSet, basename="operator")
router.register(r"attendees", AttendeeViewSet, basename="attendee")
router.register(r"requests", RequestViewSet, basename="request")
# Story fe-3.1: scope-aware очередь проверки админа (read-only, IsSuperoperator).


@api_view(["GET"])
@permission_classes([IsAuthenticated])  # defense-in-depth: явно, не полагаясь на глобальный default
def rbac_check(request):
    return Response({"role": request.user.role})


urlpatterns = router.urls + [
    path("auth/login/", LoginView.as_view(), name="api_login"),
    path("auth/logout/", LogoutView.as_view(), name="api_logout"),
    path("auth/me/", MeView.as_view(), name="api_me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="api_change_password"),
    path("rbac-check/", rbac_check, name="rbac_check"),
    path("csrf/", csrf_cookie, name="csrf_cookie"),
    path("directories/", directories, name="directories"),
]
