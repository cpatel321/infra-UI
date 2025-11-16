from django.contrib import admin
from .models import OSMFile, ComputationLog


@admin.register(OSMFile)
class OSMFileAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'status', 'uploaded_at', 'processed_at')
    list_filter = ('status', 'uploaded_at')
    readonly_fields = ('uploaded_at', 'processed_at')


@admin.register(ComputationLog)
class ComputationLogAdmin(admin.ModelAdmin):
    list_display = ('osm_file', 'num_vehicles', 'computation_time', 'total_length_m', 'total_nodes', 'computed_at')
    list_filter = ('num_vehicles', 'computed_at')
    readonly_fields = ('computed_at',)
    search_fields = ('osm_file__file_name',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('osm_file')
