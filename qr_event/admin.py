from django.contrib import admin

from .models import QrIin


@admin.register(QrIin)
class HistoricalQrAdmin(admin.ModelAdmin):
    fields = ("id", "created_at", "updated_at")
    readonly_fields = fields
    list_display = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
