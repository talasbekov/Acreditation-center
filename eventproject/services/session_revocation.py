"""Session generation for the Django user, independent of the operator profile."""

from django.contrib.auth.models import User
from django.db.models import F

from eventproject.models import UserSessionGeneration


SESSION_GENERATION_KEY = "operator_access_generation"


def active_generation(user_id):
    row = User.objects.filter(pk=user_id, is_active=True).values_list("session_generation__generation").first()
    if row is None:
        return None
    return row[0] or 0


def revoke_user_sessions(user_id):
    # The caller holds the User row lock until the status and generation commit together.
    marker, created = UserSessionGeneration.objects.get_or_create(user_id=user_id)
    if not created:
        UserSessionGeneration.objects.filter(pk=marker.pk).update(generation=F("generation") + 1)
