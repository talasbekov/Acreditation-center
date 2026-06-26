from django.utils import timezone
from django.conf import settings

from django.db import models
from django.db import IntegrityError
from django.contrib.auth.models import User

from eventproject.fernet_fields import EncryptedCharField
from eventproject.state_machine import (
    ATTENDEE_STATUS_CHOICES,
    ATTENDEE_STATUSES,
    AttendeeStatus,
)


IIN_ENCRYPTION_HELP_TEXT = (
    "ИИН зашифрован at rest через django-fernet-fields. "
    "Прямой фильтр Attendee.objects.filter(iin=...) невозможен. "
    "Используйте validators/iin.py для валидации перед сохранением."
)


class Event(models.Model):
    name_kaz = models.CharField(max_length=128, null=True, blank=True)
    name_rus = models.CharField(max_length=128, null=True, blank=True)
    name_eng = models.CharField(max_length=128, null=True, blank=True)
    event_code = models.CharField(max_length=20, null=True, blank=True)
    date_start = models.DateField(null=True, blank=True)
    date_end = models.DateField(null=True, blank=True)
    city_code = models.CharField(max_length=20, null=True, blank=True)

    # New fields for Story 2.2
    title = models.CharField(max_length=255, null=True, blank=True, help_text="Заголовок (Story 2.2)")
    description = models.TextField(null=True, blank=True, help_text="Описание (Story 2.2)")
    start_date = models.DateField(null=True, blank=True, help_text="Дата начала (Story 2.2)")
    end_date = models.DateField(null=True, blank=True, help_text="Дата окончания (Story 2.2)")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events_created",
        help_text="Кто создал (Story 2.2)"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.title or self.name_rus or f"Event {self.id}"


class Category(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="categories",
        help_text="Мероприятие (Story 2.2)"
    )
    name = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        # BE-7: в одном мероприятии не должно быть двух одноимённых категорий.
        constraints = [
            models.UniqueConstraint(
                fields=["event", "name"], name="uniq_category_event_name"
            ),
        ]

    def __str__(self):
        return f"{self.event.title or self.event.name_rus} - {self.name}"


class Operator(models.Model):
    ROLE_CHOICES = [
        ("superuser", "Суперпользователь"),
        ("superoperator", "Супероператор"),
        ("operator", "Оператор"),
        ("user", "Пользователь"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    events = models.ManyToManyField(Event, blank=True)
    patronymic = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=20)
    workplace = models.CharField(max_length=128, default="")
    is_accreditator = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="operator")

    # Story 2.3 — онбординг операторов (авто-генерация credentials + email)
    EMAIL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("error", "Error"),
    ]
    email_status = models.CharField(
        max_length=20, choices=EMAIL_STATUS_CHOICES, default="pending"
    )
    credentials_sent_at = models.DateTimeField(null=True, blank=True)
    # default=False: форс смены пароля включается ТОЛЬКО для операторов, созданных
    # авто-генерацией (services.create_operator выставляет True явно, AC-5). Иначе
    # все существующие/legacy операторы были бы принудительно сброшены.
    force_password_change = models.BooleanField(default=False)
    # Story 2.3 (review): опциональная привязка оператора к категории (AC-1 category_id).
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operators",
    )

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name


def _user_role(self):
    if self.is_superuser:
        return "superuser"
    try:
        return self.operator.role
    except Operator.DoesNotExist:
        return "user"


User.role = property(_user_role)


class OperatorAccessEvent(models.Model):
    """Story 2.4 — персистентная история доступа оператора.

    Queryable-источник для детального вида реестра. `audit_log` (Story 1.5)
    пишет только structured JSON-логи и НЕ запрашивается через ORM, поэтому
    история действий, отображаемая в UI/API, хранится здесь. События пишутся
    из views (created / login / password_changed / deactivated / reactivated).
    """

    EVENT_TYPE_CHOICES = [
        ("created", "created"),
        ("login", "login"),
        ("password_changed", "password_changed"),
        ("deactivated", "deactivated"),
        ("reactivated", "reactivated"),
    ]

    operator = models.ForeignKey(
        Operator, on_delete=models.CASCADE, related_name="access_events"
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    # Кто совершил действие: для админ-операций (deactivate) — Супероператор;
    # для login/password_changed — сам оператор. SET_NULL: история переживает
    # удаление актора.
    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    ip = models.CharField(max_length=45, blank=True, default="")
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.operator_id}:{self.event_type}@{self.timestamp:%Y-%m-%dT%H:%M:%S}"


class Request(models.Model):
    name = models.CharField(max_length=128)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    date_created = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        Operator, on_delete=models.CASCADE, related_name="created_operator"
    )
    registration_time = models.DateTimeField()
    exported_by = models.ForeignKey(
        Operator,
        on_delete=models.CASCADE,
        related_name="exported_operator",
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name


def event_photo_directory_path(instance, filename):
    return "event_{0}/attendee_photos/{1}".format(instance.request.event.id, filename)


def event_document_directory_path(instance, filename):
    return "event_{0}/attendee_documents/{1}".format(
        instance.request.event.id, filename
    )


class Attendee(models.Model):
    surname = models.CharField(max_length=128)
    firstname = models.CharField(max_length=128)
    patronymic = models.CharField(max_length=128, null=True, blank=True)
    birthDate = models.DateField(null=True, blank=True)
    post = models.CharField(max_length=500)
    countryId = models.CharField(max_length=30)
    docTypeId = models.CharField(max_length=30)
    docSeries = models.CharField(max_length=128)
    iin = EncryptedCharField(
        max_length=12,
        null=True,
        blank=True,
        help_text=IIN_ENCRYPTION_HELP_TEXT,
    )
    docNumber = models.CharField(max_length=20, null=True, blank=True)
    docBegin = models.DateField(null=True, blank=True)
    docEnd = models.DateField(null=True, blank=True)
    docIssue = models.CharField(max_length=255)
    photo = models.ImageField(upload_to=event_photo_directory_path, blank=True)
    docScan = models.ImageField(upload_to=event_document_directory_path, blank=True)
    sexId = models.CharField(max_length=20)
    dateAdd = models.DateTimeField()
    visitObjects = models.CharField(max_length=1024)
    transcription = models.CharField(max_length=255)
    request = models.ForeignKey(Request, on_delete=models.CASCADE)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendees",
        help_text="Категория (Story 2.2)"
    )
    dateEnd = models.DateField(null=True, blank=True)
    stickId = models.CharField(max_length=20, default="")
    # Story 3.2: резидент РК (countryId == settings.KZ_COUNTRY_ID) → True.
    # Residency-логика (validators/residency.py) выставляет явно при создании/
    # обновлении. default=True — KZ-центрично (исторические строки → True).
    is_resident = models.BooleanField(default=True)
    # Story 3.3: конечный автомат статусов (см. eventproject/state_machine.py).
    # Применение переходов (audit/edit-lock/submit-проверки) — Story 3.4.
    status = models.CharField(
        max_length=20,
        choices=ATTENDEE_STATUS_CHOICES,
        default=AttendeeStatus.DRAFT,
    )

    class Meta:
        # BE-9: статус ограничен FSM-набором и на уровне БД — прямой
        # `attendee.status="bogus"; save()` отклоняется (не только форма/сериализатор).
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=list(ATTENDEE_STATUSES)),
                name="attendee_status_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        # Story 4.2 (review): пустой ИИН храним как NULL, не "".
        # iin — EncryptedCharField, фильтрация по значению невозможна, поэтому
        # единственный надёжный маркер «ИИН не заполнен» — IS NULL. "" обходил бы
        # флаг дашборда (Story 4.2) и любую isnull-проверку.
        if self.iin == "":
            self.iin = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.firstname + " " + (self.iin or "")


class ExportLog(models.Model):
    """
    Отслеживает историю delta-экспортов для Epic 4.

    Delta-фильтр для следующего экспорта:
        Attendee.objects.filter(dateAdd__gt=last_export.exported_before,
                                request__event=export_log.event)

    ВАЖНО: поле участника называется Attendee.dateAdd, а НЕ created_at.
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        help_text="Мероприятие, для которого был выполнен экспорт",
    )
    category = models.ForeignKey(
        Request,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Категория участников (Request) внутри мероприятия; null = весь event",
    )
    # Граница delta для экспорта. Используется как:
    # Attendee.objects.filter(dateAdd__gt=exported_before)
    exported_before = models.DateTimeField(
        help_text="Граница delta: участники с dateAdd > этого значения считаются новыми",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Пользователь, запустивший экспорт; null для системных/scheduled задач",
    )
    attendee_count = models.IntegerField(
        help_text="Количество участников, включённых в данный экспорт",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        cat = f" / {self.category.name}" if self.category else ""
        return f"ExportLog {self.event}{cat} @ {self.exported_before}"


class AuditLogQuerySet(models.QuerySet):
    """Append-only: блокирует bulk-мутации портируемо (SQLite + Postgres).

    Review hd-4.1 (AC-3): model-level `save`/`delete` ловят только ORM-instance;
    `QuerySet.update()/.delete()` их минуют. Этот guard закрывает bulk-путь на
    всех БД (Postgres-триггер — последняя линия против сырого SQL мимо ORM).
    """

    def update(self, *args, **kwargs):
        raise IntegrityError("AuditLog is append-only: bulk UPDATE is forbidden")

    def delete(self, *args, **kwargs):
        raise IntegrityError("AuditLog is append-only: bulk DELETE is forbidden")


class AuditLog(models.Model):
    """Story hd-4.1: append-only журнал значимых действий (FR-12).

    Durable-зеркало stdout-аудита (`eventproject/audit.py`). Append-only на трёх
    слоях: model-guard (`save`/`delete`) + manager-guard (bulk `update`/`delete`,
    портируемо) + Postgres-триггер BEFORE UPDATE/DELETE (миграция 0025, raw SQL).
    `actor_id` — снимок id (НЕ FK): удаление User не трогает журнал и не конфликтует
    с append-only-триггером. ИИН в `extra` хранится МАСКИРОВАННЫМ (вычистка на write-path).
    """

    objects = AuditLogQuerySet.as_manager()

    actor_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Снимок id актора (НЕ FK — append-only аудит хранит историческую ссылку; удаление User не трогает журнал). null для system/Celery",
    )
    role = models.CharField(max_length=32)
    action = models.CharField(max_length=64, db_index=True)
    obj_type = models.CharField(max_length=64)
    obj_id = models.CharField(max_length=64, blank=True, default="")
    ip = models.CharField(max_length=45, null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["obj_type", "obj_id"]),
        ]

    def __str__(self):
        return (
            f"AuditLog {self.action} {self.obj_type}:{self.obj_id} "
            f"@ {self.created_at:%Y-%m-%dT%H:%M:%S}"
            if self.created_at
            else f"AuditLog {self.action} {self.obj_type}:{self.obj_id}"
        )

    def save(self, *args, **kwargs):
        # AC-3 append-only: запрещаем UPDATE существующей строки (model-level
        # guard — портируемо, ловит ORM-путь и на SQLite). Bulk-`QuerySet.update`
        # минует этот guard — для прода его блокирует Postgres-триггер (миграция).
        if self.pk is not None:
            raise IntegrityError("AuditLog is append-only: UPDATE is forbidden")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # AC-3 append-only: запрещаем DELETE (model-level; bulk — Postgres-триггер).
        raise IntegrityError("AuditLog is append-only: DELETE is forbidden")
