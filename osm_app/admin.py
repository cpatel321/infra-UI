from django.contrib import admin
from .models import OSMFile, ComputationLog, Depot, WardConfiguration, Ward


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


@admin.register(Depot)
class DepotAdmin(admin.ModelAdmin):
    list_display = ('name', 'lat', 'lon', 'capacity_kg', 'active', 'created_at')
    list_filter = ('active', 'created_at')
    search_fields = ('name', 'address')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'address', 'active')
        }),
        ('Location', {
            'fields': ('lat', 'lon')
        }),
        ('Capacity', {
            'fields': ('capacity_kg',)
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )


@admin.register(WardConfiguration)
class WardConfigurationAdmin(admin.ModelAdmin):
    list_display = ('osm_file', 'num_wards', 'ward_layout', 'total_area_km2', 'created_at')
    list_filter = ('ward_layout', 'created_at')
    search_fields = ('osm_file__file_name',)
    readonly_fields = ('created_at',)


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ('ward_number', 'config', 'area_km2', 'population', 'total_roads', 'has_valid_data', 'is_connected')
    list_filter = ('has_valid_data', 'is_connected', 'population_source', 'config')
    search_fields = ('ward_number', 'config__osm_file__file_name')
    readonly_fields = ('last_validated', 'computed_at')
    fieldsets = (
        ('Ward Identity', {
            'fields': ('config', 'ward_number')
        }),
        ('Geographic Bounds', {
            'fields': ('min_lat', 'max_lat', 'min_lon', 'max_lon', 'centroid_lat', 'centroid_lon')
        }),
        ('Statistics', {
            'fields': ('area_km2', 'total_nodes', 'total_roads', 'total_length_m')
        }),
        ('Population & Waste', {
            'fields': ('population', 'population_source', 'population_density_per_km2', 
                      'waste_per_capita_kg', 'vehicle_capacity_kg')
        }),
        ('Depot Assignment', {
            'fields': ('assigned_depot', 'depot_distance_km')
        }),
        ('Validation', {
            'fields': ('is_connected', 'has_valid_data', 'validation_warnings', 'last_validated')
        }),
        ('Routing Results', {
            'fields': ('num_vehicles', 'computation_time', 'computed_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('config', 'config__osm_file', 'assigned_depot')
