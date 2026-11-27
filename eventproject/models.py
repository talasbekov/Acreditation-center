import uuid

from django.utils import timezone
from django.conf import settings

from django.db import models
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
        role = self.operator.role
        return role if role in ("operator", "superoperator") else "user"
    except Operator.DoesNotExist:
        return "user"


User.role = property(_user_role)


class UserSessionGeneration(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name="session_generation",
    )
    generation = models.PositiveBigIntegerField(default=1)


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
    # Этап C: последнее решение проверяющего. Причина возврата видна оператору до
    # повторной отправки; полная история — в audit_log.
    review_comment = models.TextField(blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
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
        # P2: список участников в API сортируется по дате добавления и выдаётся
        # страницами. Без индекса PostgreSQL сортирует все строки доступных
        # мероприятий (150 тыс. — ~77 мс на страницу), с индексом — читает первые 50.
        indexes = [
            models.Index(fields=["-dateAdd"], name="attendee_dateadd_idx"),
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
    Пакет delta-экспорта (Epic 4, этап C).

    Состав следующего пакета определяется фактом готовности, а не датой
    добавления: в него входят все участники категории со статусом `ready`.
    Переход ready → exported терминальный и выполняется в той же транзакции,
    что и создание записи, поэтому участник попадает ровно в один пакет, в том
    числе если его одобрили позже предыдущей выгрузки.

    Пакет неизменяем: `package_id`, упорядоченный `attendee_ids` и `manifest`
    (SHA-256 каждого элемента ZIP) позволяют выдать тот же архив повторно и
    отказать, если исходные данные с тех пор изменились. Сам ZIP с ПД на сервере
    не хранится. Подтверждение получателя фиксируется отдельно.
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
    package_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Неизменяемый идентификатор пакета выгрузки",
    )
    # Момент формирования пакета. Также служит меткой времени элементов ZIP,
    # чтобы повторная выдача давала побайтно тот же архив.
    exported_before = models.DateTimeField(
        help_text="Момент формирования пакета",
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
    # null у пакетов, сформированных до миграции 0027: их состав не записывался,
    # повторная выдача для них недоступна.
    attendee_ids = models.JSONField(
        null=True,
        blank=True,
        help_text="Упорядоченный список ID участников пакета",
    )
    manifest = models.JSONField(
        null=True,
        blank=True,
        help_text="SHA-256 каждого элемента архива: {имя в ZIP: hex}",
    )
    archive_name = models.CharField(max_length=255, blank=True, default="")
    archive_sha256 = models.CharField(max_length=64, blank=True, default="")
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Когда получатель подтвердил приём пакета",
    )
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Кто отметил подтверждение получателя",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    @property
    def can_redownload(self):
        return self.attendee_ids is not None and bool(self.manifest)

    def __str__(self):
        cat = f" / {self.category.name}" if self.category else ""
        return f"ExportLog {self.event}{cat} @ {self.exported_before}"


class PartnerReceipt(models.Model):
    """Квитанция приёма одной анкеты партнёра (этап C).

    Одна строка на (источник, мероприятие, идентификатор анкеты у партнёра).
    Повторно присланная анкета не создаёт второго участника: партнёру повторно
    уходит сохранённое подтверждение. ПД здесь не хранятся — только исход,
    тело подтверждения (коды и причины без значений полей) и его доставка.
    """

    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    OUTCOMES = [
        (ACCEPTED, "Принята"),
        (DUPLICATE, "Дубль"),
        (REJECTED, "Отклонена"),
    ]

    source = models.CharField(max_length=32)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="+")
    external_id = models.CharField(max_length=128)
    attendee = models.ForeignKey(
        Attendee, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    outcome = models.CharField(max_length=16, choices=OUTCOMES)
    ack_payload = models.JSONField(help_text="Тело подтверждения партнёру; повторяется при повторной анкете")
    received_at = models.DateTimeField(auto_now_add=True)
    ack_attempts = models.PositiveIntegerField(default=0)
    acked_at = models.DateTimeField(null=True, blank=True, help_text="Когда партнёр принял подтверждение")
    last_ack_status = models.IntegerField(null=True, blank=True, help_text="HTTP-статус последней попытки; 0 — сбой сети")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "event", "external_id"], name="partner_receipt_unique",
            ),
        ]

    def __str__(self):
        return f"{self.source}:{self.external_id} → {self.outcome}"
