from django.utils import timezone

from django.db import models
from django.contrib.auth.models import User


class Event(models.Model):
    name_kaz = models.CharField(max_length=128)
    name_rus = models.CharField(max_length=128)
    name_eng = models.CharField(max_length=128)
    event_code = models.CharField(max_length=20)
    date_start = models.DateField()
    date_end = models.DateField()
    city_code = models.CharField(max_length=20)

    def __str__(self):
        return self.name_rus


class Operator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    events = models.ManyToManyField(Event, blank=True)
    patronymic = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=20)
    workplace = models.CharField(max_length=128, default="")
    is_accreditator = models.BooleanField(default=False)

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name


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
    iin = models.CharField(max_length=12, null=True, blank=True)
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
    dateEnd = models.DateField(null=True, blank=True)
    stickId = models.CharField(max_length=20, default="")

    def __str__(self):
        return self.firstname + " " + self.iin
