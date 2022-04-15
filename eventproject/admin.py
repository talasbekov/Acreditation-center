from django.contrib.admin import AdminSite
from django.contrib import admin

from .models import Event, Attendee, Operator, Request

#class MyAdminSite(AdminSite):
#    site_header = 'Monty Python administration'

#admin_site = MyAdminSite(name='admin')
#admin_site.register(Event)
#admin_site.register(Attendee)
#admin_site.register(Operator)
#admin_site.register(Request)

admin.site.register(Event)
admin.site.register(Operator)
admin.site.register(Request)
admin.site.register(Attendee)
