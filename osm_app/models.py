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
