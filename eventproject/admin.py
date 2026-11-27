from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db import transaction
from .models import Event, Operator, Request, Attendee
from .permissions import can_manage_operator_account
from .services.session_revocation import revoke_user_sessions


admin.site.unregister(User)


@admin.register(User)
class SessionAwareUserAdmin(UserAdmin):
    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if not change:
            return super().save_model(request, obj, form, change)
        previous = User.objects.select_for_update().get(pk=obj.pk)
        if "is_active" not in form.changed_data:
            obj.is_active = previous.is_active
        super().save_model(request, obj, form, change)
        if previous.is_active and not obj.is_active:
            revoke_user_sessions(obj.pk)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    actions = None

    list_display = ("id", "name_rus", "name_kaz", "name_eng", "event_code", "date_start", "date_end", "city_code")
    search_fields = ("name_rus", "name_kaz", "name_eng", "event_code", "city_code")
    list_filter = ("date_start", "date_end", "city_code")


@admin.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "patronymic", "phone_number", "workplace", "is_accreditator")
    search_fields = ("user__first_name", "user__last_name", "patronymic", "phone_number", "workplace")
    list_filter = ("is_accreditator", "workplace")

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ()
        return ("user", "role", "is_accreditator") if obj else ("role", "is_accreditator")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (
            obj is None or can_manage_operator_account(request.user, obj)
        )

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            # Django checks this case for bulk-delete actions.
            return request.user.is_superuser and super().has_delete_permission(request, obj)
        return super().has_delete_permission(request, obj) and can_manage_operator_account(request.user, obj)


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "event", "status", "date_created", "created_by", "registration_time", "exported_by")
    search_fields = ("name", "status", "event__name_rus", "created_by__user__username", "exported_by__user__username")
    list_filter = ("status", "date_created", "registration_time")


@admin.register(Attendee)
class AttendeeAdmin(admin.ModelAdmin):
    list_display = ("id", "surname", "firstname", "patronymic", "post", "countryId", "request")
    search_fields = ("surname", "firstname", "patronymic", "post", "countryId", "docNumber")
    list_filter = ("countryId", "sexId", "dateAdd", "dateEnd")
