"""Story 2.3 — отправка учётных данных оператора по email.

Использует Django `send_mail`. Настройки SMTP читаются из `settings` (которые в
свою очередь берутся из `.env`). При ошибке SMTP функция пробрасывает исключение —
вызывающий код (OperatorViewSet) ловит его и выставляет `email_status="error"`,
не откатывая создание оператора (AC-3).
"""

from django.conf import settings
from django.core.mail import send_mail


def send_operator_credentials(operator, temporary_password):
    """Отправляет оператору письмо с логином, временным паролем и ссылкой на вход.

    Бросает исключение при недоступности/ошибке SMTP (fail_silently=False).
    """
    user = operator.user
    login_url = getattr(settings, "OPERATOR_LOGIN_URL", "/user_login/")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@accreditation.local")

    subject = "Доступ к системе аккредитации"
    message = (
        f"Здравствуйте, {user.first_name} {user.last_name}!\n\n"
        f"Для вас создана учётная запись оператора в системе аккредитации.\n\n"
        f"Логин: {user.username}\n"
        f"Временный пароль: {temporary_password}\n"
        f"Ссылка для входа: {login_url}\n\n"
        f"При первом входе система попросит сменить пароль.\n"
    )

    send_mail(
        subject,
        message,
        from_email,
        [user.email],
        fail_silently=False,
    )
