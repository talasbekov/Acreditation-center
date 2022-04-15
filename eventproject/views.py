from django.shortcuts import render
from django.http import HttpResponse
from eventproject.models import Event, Operator
from eventproject.forms import EventForm
import datetime
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User

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
	return render(request, 'index.html', context=context_dict)

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
