from django.db import models
from django.contrib.auth.models import User 

class Event(models.Model):
	name_kaz = models.CharField(max_length=128)
	name_rus = models.CharField(max_length=128)
	name_eng = models.CharField(max_length=128)
	event_code = models.CharField(max_length=20)
	date_start = models.DateField()
	date_end = models.DateField()
	def __str__(self):
		return self.name_rus

class Operator(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE)
	events = models.ManyToManyField(Event, blank=True)
	patronymic = models.CharField(max_length=128)
	phone_number = models.CharField(max_length=20)
	workplace = models.CharField(max_length = 128, default="")
	is_accreditator = models.BooleanField(default=False)

	def __str__(self):
		return self.user.first_name


class Request(models.Model):
	name = models.CharField(max_length=128)
	event = models.ForeignKey(Event, on_delete=models.CASCADE)
	status = models.CharField(max_length=20)
	date_created = models.DateTimeField()
	created_by = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="created_operator")
	registration_time = models.DateTimeField()
	exported_by = models.ForeignKey(Operator, on_delete=models.CASCADE, related_name="exported_operator")

	def __str__(self):
		return self.name

class Attendee(models.Model):
	surname = models.CharField(max_length=128)
	firstname = models.CharField(max_length=128)
	patronymic = models.CharField(max_length=128)
	birthDate = models.DateField()
	post = models.CharField(max_length=128)
	countryId = models.CharField(max_length=30)
	docTypeId = models.CharField(max_length=30)
	docSeries = models.CharField(max_length=128)
	iin = models.CharField(max_length=12)
	docNumber = models.CharField(max_length=20)
	docBegin = models.DateField()
	docEnd = models.DateField()
	docIssue = models.CharField(max_length=50)	
	photo = models.ImageField(upload_to='attendee_photos', blank=True)
	docScan = models.ImageField(upload_to='attendee_document', blank=True)
	sexId = models.CharField(max_length=20)
	dateAdd = models.DateTimeField()
	visitObjects = models.CharField(max_length=200)
	transcription = models.CharField(max_length=128)
	request = models.ForeignKey(Request, on_delete=models.CASCADE)
	dateEnd = models.DateField()

	def __str__(self):
		return self.firstname


