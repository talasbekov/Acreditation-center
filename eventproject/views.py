from django.shortcuts import render
from django.http import HttpResponse
from eventproject.models import Event, Operator, Request, Attendee
from eventproject.forms import EventForm
import datetime
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta
from django.contrib.auth import logout
from directories.models import Sex, Country, DocumentType
from django.forms.models import model_to_dict
import json

# Create your views here.

def index(request):
		# Construct a dictionary to pass to the template engine as its context.
	# Note the key boldmessage is the same as {{ boldmessage }} in the template!
#	context_dict = {'boldmessage': "Crunchy, creamy, cookie, candy, cupcake!"}
#	context_dict['sitename'] = "Shyntas"
	event_list = Event.objects.all()
	operators = Operator.objects.all()
	context_dict = {'events': event_list}
	context_dict['operators'] = operators
	# Return a rendered response to send to the client.
	# We make use of the shortcut function to make our lives easier.
	# Note that the first parameter is the template we wish to use.
	return render(request, 'gov.html', context=context_dict)

def add_event(request):
	form = EventForm()

	if request.method == 'POST':
		form = EventForm(request.POST)

		if form.is_valid():
			form.save(commit=True)
			return index(request)
		else:
			print(form.errors)
	return render(request, 'add_event.html', {'form': form})

def create_event(request):
	if request.method == 'POST':
		name_rus = request.POST['name_rus']
		name_kaz = request.POST['name_kaz']
		name_eng = request.POST['name_eng']
		event_code = request.POST['event_code']
		date_start = request.POST['date_start']
		date_end = request.POST['date_end']
		event = Event(name_kaz = name_kaz, name_rus = name_rus, name_eng = name_eng, event_code = event_code,
					  date_start = date_start, date_end = date_end)
		event.save()

	return HttpResponseRedirect('/')

def add_operator(request):
	if request.method == 'POST':
		first_name = request.POST['first_name']
		last_name = request.POST['last_name']
		patronymic = request.POST['patronymic']
		login = request.POST['login']
		phone_number = request.POST['phone_number']
		password = "Astana2006!"
		event_code = request.POST['event_code']
		workplace = request.POST['workplace']

		user = User(username=login,
                                 first_name=first_name,
								last_name = last_name,
                                 password=password)
		user.save()
		event = Event.objects.get(pk = event_code)
		operator = Operator(user=user, phone_number = phone_number, patronymic=patronymic, workplace=workplace)
		operator.save()
		operator.events.add(event)
		operator.save()

	return HttpResponseRedirect('/')

@login_required(login_url='/user_login/')
def application(request):
	if not request.user.is_authenticated:
		return HttpResponse("You are logged in.")
	user = request.user
	operator = Operator.objects.get(user=user)
	if not operator:
		return HttpResponse("You are logged in.")
	startdate = date.today()
	enddate = startdate + timedelta(days=600)
	events = operator.events.filter(date_start__range=[startdate, enddate])
	return render(request, 'gov2.html', {'user': user, 'operator':operator, 'events': events})

@login_required(login_url='/user_login/')
def create_request(request, event_id):
	context_dict = {}
	try:
		event = Event.objects.get(pk=event_id)
		context_dict['event'] = event
		operator = Operator.objects.get(user=request.user)
		request_set = Request.objects.filter(event = event, status = 'Sent')
		sexs = Sex.objects.all()
		context_dict['sexs'] = sexs
		countries = Country.objects.all()
		context_dict['countries'] = countries
		document_types = DocumentType.objects.all()
		context_dict['document_types'] = document_types
		list_of_requests =[]
		for req in request_set:
			request_dict = model_to_dict(req)
			attendees = Attendee.objects.filter(request=req)
			list_of_attendees = []
			for attendee in attendees:
				attendee_dict = model_to_dict(attendee)
				list_of_attendees.append(attendee_dict)
			request_dict['attendees'] = list_of_attendees
			serialized_request = json.dumps(request_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False)
			file = open(request_dict['name']+'.txt', 'w')
			file.write(serialized_request)
			file.close()
			list_of_requests.append(request_dict)
		#print("ai  m here")
		event_dict = model_to_dict(event)
		event_dict['requests'] = list_of_requests
		serialized_event = json.dumps(event_dict, indent=4, sort_keys=True, default=str, ensure_ascii=False)
		print(serialized_event)
		file = open('event_json.txt', 'w')
		file.write(serialized_event)
		file.close()

	except Event.DoesNotExist:
		return HttpResponse("Could not find event")
	return render(request, 'gov3.html', context_dict)

@login_required(login_url='/user_login/')
def user_logout(request):
	logout(request)
	return HttpResponseRedirect('/user_login/')

def user_login(request):
	context = RequestContext(request)
	if request.method == 'POST':
		username = request.POST['username']
		password = request.POST['password']
		user = authenticate(username=username, password=password)
		if user is not None:
			if user.is_active:
				login(request, user)
				return HttpResponseRedirect('/application/')
			else:
				return HttpResponse("Your account is suspended")
		else:
			return render(request, 'gov.html', context={'error_message':'invalid login details'})
	return render(request, 'gov.html', context={})
	#return render_to_response('gov.html', , context)
