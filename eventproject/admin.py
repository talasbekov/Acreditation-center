from django.contrib import admin

from .models import Event, Attendee, Operator, Request


admin.site.register(Event)
admin.site.register(Operator)
admin.site.register(Request)
admin.site.register(Attendee)
