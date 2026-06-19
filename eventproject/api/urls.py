from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view
from rest_framework.response import Response
from eventproject.views.event import EventViewSet


router = DefaultRouter()
router.register(r"events", EventViewSet, basename="event")


@api_view(["GET"])
def rbac_check(request):
    return Response({"role": request.user.role})


urlpatterns = router.urls + [
    path("rbac-check/", rbac_check, name="rbac_check"),
]
