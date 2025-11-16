from django.db import models
from django.utils import timezone
import os


class OSMFile(models.Model):
    """Model to store uploaded OSM files and their processed versions"""
    
    original_file = models.FileField(upload_to='osm_files/original/')
    processed_file = models.FileField(upload_to='osm_files/processed/', null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    file_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, default='uploaded', 
                             choices=[
                                 ('uploaded', 'Uploaded'),
                                 ('processing', 'Processing'),
                                 ('processed', 'Processed'),
                                 ('error', 'Error')
                             ])
    
    # Bounding box for cropping (if applied)
    min_lat = models.FloatField(null=True, blank=True)
    max_lat = models.FloatField(null=True, blank=True)
    min_lon = models.FloatField(null=True, blank=True)
    max_lon = models.FloatField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.file_name} - {self.status}"
    
    def get_absolute_url(self):
        return f"/osm/{self.id}/"


class ComputationLog(models.Model):
    """Log computation performance metrics for optimization analysis"""
    
    osm_file = models.ForeignKey(OSMFile, on_delete=models.CASCADE, related_name='computation_logs')
    num_vehicles = models.IntegerField()
    computation_time = models.FloatField(help_text="Time in seconds")
    total_length_m = models.FloatField(help_text="Total road length in meters")
    total_nodes = models.IntegerField()
    total_roads = models.IntegerField()
    computed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-computed_at']
        indexes = [
            models.Index(fields=['osm_file', '-computed_at']),
            models.Index(fields=['num_vehicles']),
        ]
    
    def __str__(self):
        return f"{self.osm_file.file_name} - {self.num_vehicles} vehicles - {self.computation_time:.2f}s"


class WardConfiguration(models.Model):
    """Configuration for dividing an area into multiple wards"""
    
    osm_file = models.ForeignKey(OSMFile, on_delete=models.CASCADE, related_name='ward_configs')
    num_wards = models.IntegerField(default=4)
    total_area_km2 = models.FloatField(default=0.0, help_text="Total area in square kilometers")
    area_per_ward_km2 = models.FloatField(default=0.0, help_text="Average area per ward in square kilometers")
    ward_layout = models.CharField(max_length=50, default='auto_grid', 
                                   choices=[
                                       ('auto_grid', 'Auto (Square Grid)'),
                                       ('manual', 'Manual'),
                                   ])
    grid_rows = models.IntegerField(null=True, blank=True, help_text="Number of rows in grid layout")
    grid_cols = models.IntegerField(null=True, blank=True, help_text="Number of columns in grid layout")
    ward_dimensions_km = models.CharField(max_length=100, blank=True, help_text="Approximate dimensions (e.g., '1.43 × 1.28 km')")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['osm_file', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.osm_file.file_name} - {self.num_wards} wards"


class Ward(models.Model):
    """Individual ward within a ward configuration"""
    
    config = models.ForeignKey(WardConfiguration, on_delete=models.CASCADE, related_name='wards')
    ward_number = models.IntegerField(default=1)
    
    # Bounding box for this ward
    min_lat = models.FloatField(default=0.0)
    max_lat = models.FloatField(default=0.0)
    min_lon = models.FloatField(default=0.0)
    max_lon = models.FloatField(default=0.0)
    
    # Centroid (depot location for this ward)
    centroid_lat = models.FloatField(default=0.0)
    centroid_lon = models.FloatField(default=0.0)
    
    # Ward statistics
    area_km2 = models.FloatField(default=0.0, help_text="Ward area in square kilometers")
    total_nodes = models.IntegerField(default=0)
    total_roads = models.IntegerField(default=0)
    total_length_m = models.FloatField(default=0.0, help_text="Total road length in meters")
    
    # Routing results
    num_vehicles = models.IntegerField(null=True, blank=True)
    routes_geojson = models.JSONField(null=True, blank=True, help_text="Computed routes in GeoJSON format")
    computation_time = models.FloatField(null=True, blank=True, help_text="Time in seconds")
    computed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['config', 'ward_number']
        indexes = [
            models.Index(fields=['config', 'ward_number']),
        ]
        unique_together = [['config', 'ward_number']]
    
    def __str__(self):
        return f"Ward {self.ward_number} ({self.config.osm_file.file_name})"

