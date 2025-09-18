from django.contrib import admin
from .models import Event, Operator, Request, Attendee


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "name_rus", "name_kaz", "name_eng", "event_code", "date_start", "date_end", "city_code")
    search_fields = ("name_rus", "name_kaz", "name_eng", "event_code", "city_code")
    list_filter = ("date_start", "date_end", "city_code")


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "patronymic", "phone_number", "workplace", "is_accreditator")
    search_fields = ("user__first_name", "user__last_name", "patronymic", "phone_number", "workplace")
    list_filter = ("is_accreditator", "workplace")


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "event", "status", "date_created", "created_by", "registration_time", "exported_by")
    search_fields = ("name", "status", "event__name_rus", "created_by__user__username", "exported_by__user__username")
    list_filter = ("status", "date_created", "registration_time")


@admin.register(Attendee)
class AttendeeAdmin(admin.ModelAdmin):
    list_display = ("id", "surname", "firstname", "patronymic", "iin", "post", "countryId", "request")
    search_fields = ("surname", "firstname", "patronymic", "iin", "post", "countryId", "docNumber")
    list_filter = ("countryId", "sexId", "dateAdd", "dateEnd")
