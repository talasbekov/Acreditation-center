from django import forms
from eventproject.models import Event, Operator, Request, Attendee


class EventForm(forms.ModelForm):
    name_kaz = forms.CharField(max_length=128, help_text="Please enter the event name.")
    name_rus = forms.CharField(max_length=128, help_text="Please enter the event name.")

    class Meta:
        model = Event
        fields = ("name_kaz", "name_rus")
