"""Operator invitation and password reset. The recipient selects the password."""

import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.views import PasswordResetConfirmView
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from eventproject.models import Operator
from eventproject.services.session_revocation import active_generation

logger = logging.getLogger("eventproject")


class OperatorTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "eventproject.operator_activation"

    def _make_hash_value(self, user, timestamp):
        # Invalidate an outstanding invitation when the target gains privileged access.
        operator = user.operator
        value = "|".join((
            super()._make_hash_value(user, timestamp), user.email,
            str(user.is_active), str(user.is_staff), str(user.is_superuser),
            str(operator.is_accreditator), getattr(operator, "role", ""),
        ))
        generation = active_generation(user.pk)
        # Preserve previously issued links for accounts with no revocation history.
        return f"{value}|{generation}" if generation else value


operator_tokens = OperatorTokenGenerator()


def _send_operator_link(operator):
    """Return success only after the configured transport accepts one message."""
    user = operator.user
    if not user.is_active:
        return False
    try:
        validate_email(user.email)
        origin = settings.OPERATOR_PUBLIC_ORIGIN
        URLValidator(schemes=["https"])(origin)
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or parsed.username is not None
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or any(char in origin for char in ("\\", "?", "#"))):
            return False
        # Console/file/dummy transports must never receive a bearer token.
        if settings.EMAIL_BACKEND not in (
            "django.core.mail.backends.smtp.EmailBackend",
            "django.core.mail.backends.locmem.EmailBackend",
        ):
            return False
        if settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
            if not (settings.EMAIL_USE_TLS or settings.EMAIL_USE_SSL):
                return False
        path = reverse("operator-set-password", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": operator_tokens.make_token(user),
        })
        return send_mail(
            "Доступ к системе аккредитации",
            f"Логин: {user.username}\n\nЧтобы установить пароль, откройте одноразовую ссылку:\n"
            f"{origin.rstrip('/')}{path}\n\nЕсли вы не ожидали письма, обратитесь к администратору.",
            settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
        ) == 1
    except (ValidationError, ValueError):
        return False
    except Exception:
        # Transport errors may contain message contents or a recipient address.
        logger.error("Operator activation email failed for operator id=%s", operator.pk)
        return False


def send_operator_link(operator):
    sent = _send_operator_link(operator)
    operator.email_status = "sent" if sent else "error"
    fields = ["email_status"]
    if sent:
        operator.credentials_sent_at = timezone.now()
        fields.append("credentials_sent_at")
    operator.save(update_fields=fields)
    return sent


class OperatorSetPasswordView(PasswordResetConfirmView):
    template_name = "operator_set_password.html"
    success_url = "/user_login/"
    token_generator = operator_tokens

    @transaction.atomic
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def get_user(self, uidb64):
        candidate = super().get_user(uidb64)
        if candidate is None:
            return None
        users = User.objects.filter(pk=candidate.pk, is_active=True, operator__isnull=False)
        if self.request.method == "POST":
            users = users.select_for_update()
        return users.select_related("operator").first()

    def form_valid(self, form):
        response = super().form_valid(form)
        Operator.objects.filter(user=self.user, force_password_change=True).update(force_password_change=False)
        return response
