from django.contrib import admin
from .models import OSMFile


@admin.register(OSMFile)
class OSMFileAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'status', 'uploaded_at', 'processed_at')
    list_filter = ('status', 'uploaded_at')
    readonly_fields = ('uploaded_at', 'processed_at')
