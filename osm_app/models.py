from django.db import models
from django.utils import timezone
import os
import math


class Depot(models.Model):
    """Waste transfer station or vehicle garage"""
    
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    lat = models.FloatField()
    lon = models.FloatField()
    capacity_kg = models.FloatField(default=10000.0, help_text="Daily handling capacity (kg)")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.lat:.4f}, {self.lon:.4f})"


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
    
    # Population and waste data
    population = models.IntegerField(default=0, help_text="Estimated population count")
    population_source = models.CharField(
        max_length=20, 
        default='worldpop',
        choices=[
            ('manual', 'Manual Entry'),
            ('worldpop', 'WorldPop Raster'),
            ('osm', 'OSM Buildings')
        ]
    )
    population_density_per_km2 = models.FloatField(default=0.0, help_text="Population per square kilometer")
    
    # Waste generation parameters (with Indian defaults)
    waste_per_capita_kg = models.FloatField(default=0.5, help_text="Waste per person per day (kg)")
    vehicle_capacity_kg = models.FloatField(default=1000.0, help_text="Vehicle capacity (kg)")
    
    # Depot assignment
    assigned_depot = models.ForeignKey(Depot, on_delete=models.SET_NULL, null=True, blank=True, related_name='wards')
    depot_distance_km = models.FloatField(default=0.0, help_text="Distance from ward centroid to depot (km)")
    
    # Validation fields
    is_connected = models.BooleanField(default=True, help_text="All roads in ward form a connected network")
    has_valid_data = models.BooleanField(default=True, help_text="Ward has sufficient data for routing")
    validation_warnings = models.JSONField(default=list, blank=True, help_text="List of validation warnings")
    last_validated = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['config', 'ward_number']
        indexes = [
            models.Index(fields=['config', 'ward_number']),
        ]
        unique_together = [['config', 'ward_number']]
    
    def __str__(self):
        return f"Ward {self.ward_number} ({self.config.osm_file.file_name})"
    
    def update_population_from_worldpop(self):
        """
        Fetch population from WorldPop raster and update this ward
        """
        from django.conf import settings
        from .gis_utils import get_population_from_worldpop
        
        if not settings.POPULATION_RASTER_PATH.exists():
            return False
        
        bounds = {
            'min_lat': self.min_lat,
            'max_lat': self.max_lat,
            'min_lon': self.min_lon,
            'max_lon': self.max_lon
        }
        
        population = get_population_from_worldpop(
            bounds, 
            str(settings.POPULATION_RASTER_PATH)
        )
        
        self.population = population
        self.population_density_per_km2 = population / self.area_km2 if self.area_km2 > 0 else 0
        self.population_source = 'worldpop'
        self.save()
        
        return True
    
    def calculate_total_waste(self):
        """Calculate daily waste generation in kg"""
        return self.population * self.waste_per_capita_kg
    
    def suggest_vehicles(self, speed_kmh=25, time_window_hours=4, max_vehicles=20):
        """
        Calculate optimal vehicles considering BOTH capacity and time constraints
        Also accounts for depot travel time if assigned
        
        Args:
            speed_kmh: Vehicle speed (default 25 km/h)
            time_window_hours: Maximum operation time (default 4 hours)
            max_vehicles: Maximum allowed vehicles (default 20)
        
        Returns:
            dict with suggested vehicles and breakdown
        """
        # Account for depot travel time (round trip)
        depot_travel_time = 0
        if self.assigned_depot and self.depot_distance_km > 0:
            depot_travel_time = (self.depot_distance_km * 2) / speed_kmh  # hours for round trip
        
        available_time = time_window_hours - depot_travel_time
        
        if available_time <= 0:
            return {
                'error': 'Ward too far from depot',
                'depot_travel_time': depot_travel_time,
                'time_window': time_window_hours,
                'suggestion': 'Increase shift duration or assign closer depot'
            }
        
        # By capacity constraint
        total_waste = self.calculate_total_waste()
        vehicles_by_capacity = math.ceil(total_waste / self.vehicle_capacity_kg) if self.vehicle_capacity_kg > 0 else 1
        
        # By time constraint (using available time after depot travel)
        total_length_km = self.total_length_m / 1000.0
        total_time_hours = total_length_km / speed_kmh if speed_kmh > 0 else 0
        vehicles_by_time = math.ceil(total_time_hours / available_time) if available_time > 0 else 1
        
        # Take maximum (most constraining factor), but cap at max_vehicles
        suggested = min(max(vehicles_by_capacity, vehicles_by_time, 1), max_vehicles)
        
        return {
            'suggested': suggested,
            'by_capacity': vehicles_by_capacity,
            'by_time': vehicles_by_time,
            'total_waste_kg': total_waste,
            'depot_travel_time_hours': depot_travel_time,
            'available_collection_time_hours': available_time,
            'limiting_factor': 'capacity' if vehicles_by_capacity >= vehicles_by_time else 'time',
            'capped': suggested == max_vehicles and (vehicles_by_capacity > max_vehicles or vehicles_by_time > max_vehicles)
        }
    
    def suggest_vehicles_probabilistic(self, speed_kmh=25, time_window_hours=4, max_vehicles=20, confidence_level=0.95, n_simulations=5000):
        """
        Probabilistic vehicle calculation using Monte Carlo simulation
        Accounts for real-world uncertainty:
        - Traffic variability (speed varies)
        - Waste generation uncertainty (±15% from estimates)
        - Vehicle breakdowns (5% probability)
        - Weather delays (30% chance of 20% slowdown)
        
        Args:
            speed_kmh: Base vehicle speed
            time_window_hours: Maximum operation time
            max_vehicles: Maximum allowed vehicles
            confidence_level: Probability of success (0.95 = 95% confidence)
            n_simulations: Number of Monte Carlo iterations
        
        Returns:
            dict with suggested vehicles, confidence intervals, and risk analysis
        """
        import numpy as np
        
        # Base parameters
        base_waste = self.calculate_total_waste()
        total_length_km = self.total_length_m / 1000.0
        vehicle_capacity = self.vehicle_capacity_kg
        
        # Account for depot
        depot_travel_time = 0
        if self.assigned_depot and self.depot_distance_km > 0:
            depot_travel_time = (self.depot_distance_km * 2) / speed_kmh
        
        available_time = time_window_hours - depot_travel_time
        
        if available_time <= 0:
            return {
                'error': 'Ward too far from depot',
                'depot_travel_time': depot_travel_time
            }
        
        # Monte Carlo simulation
        vehicles_needed = []
        
        for _ in range(n_simulations):
            # 1. Sample traffic variability (log-normal distribution)
            # Most days normal speed, occasionally much slower
            actual_speed = np.random.lognormal(
                mean=np.log(speed_kmh),
                sigma=0.2  # 20% variability
            )
            actual_speed = max(5, min(actual_speed, speed_kmh * 1.5))  # Cap at 1.5x base speed
            
            # 2. Sample waste uncertainty (normal distribution ±15%)
            waste_std = base_waste * 0.15
            actual_waste = np.random.normal(base_waste, waste_std)
            actual_waste = max(0, actual_waste)
            
            # 3. Weather event (30% chance of 20% slowdown)
            if np.random.random() < 0.3:
                actual_speed *= 0.8
            
            # 4. Vehicle breakdown (5% probability per day)
            breakdown_penalty = 1 if np.random.random() < 0.05 else 0
            
            # Calculate vehicles for this scenario
            v_capacity = int(np.ceil(actual_waste / vehicle_capacity)) if vehicle_capacity > 0 else 1
            
            time_needed = total_length_km / actual_speed if actual_speed > 0 else 0
            v_time = int(np.ceil(time_needed / available_time)) if available_time > 0 else 1
            
            v_needed = max(v_capacity, v_time, 1) + breakdown_penalty
            vehicles_needed.append(v_needed)
        
        # Statistical analysis
        vehicles_needed = np.array(vehicles_needed)
        required_vehicles = int(np.percentile(vehicles_needed, confidence_level * 100))
        required_vehicles = min(required_vehicles, max_vehicles)
        
        mean_vehicles = float(np.mean(vehicles_needed))
        median_vehicles = float(np.median(vehicles_needed))
        std_vehicles = float(np.std(vehicles_needed))
        
        # Risk analysis - probability of completion with different vehicle counts
        risk_profile = {}
        for v in range(1, min(int(np.max(vehicles_needed)) + 1, max_vehicles + 1)):
            success_rate = float(np.mean(vehicles_needed <= v))
            risk_profile[v] = success_rate
        
        # Deterministic baseline for comparison
        deterministic = self.suggest_vehicles(speed_kmh, time_window_hours, max_vehicles)
        
        return {
            'suggested': required_vehicles,
            'confidence_level': confidence_level,
            'mean': round(mean_vehicles, 2),
            'median': median_vehicles,
            'std': round(std_vehicles, 2),
            'deterministic_suggestion': deterministic['suggested'],
            'safety_margin': required_vehicles - deterministic['suggested'],
            'risk_profile': risk_profile,
            'interpretation': f'{confidence_level*100:.0f}% chance of success with {required_vehicles} vehicles',
            'total_waste_kg': base_waste,
            'depot_travel_time_hours': depot_travel_time,
            'available_collection_time_hours': available_time
        }

