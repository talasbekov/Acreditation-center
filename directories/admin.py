from django.contrib import admin

from .models import Sex, Country, DocumentType


admin.site.register(Sex)
admin.site.register(Country)
admin.site.register(DocumentType)