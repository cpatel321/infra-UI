"""
Simple WorldPop population test for Kanpur (no visualization)
Uses Django environment - run with: python manage.py shell < test_worldpop_simple.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'osm_processor.settings')
django.setup()

from django.conf import settings
from osm_app.gis_utils import get_population_from_worldpop
import numpy as np

# Kanpur approximate bounds
KANPUR_BOUNDS = {
    'min_lat': 26.35,
    'max_lat': 26.55,
    'min_lon': 80.25,
    'max_lon': 80.45
}

print("="*80)
print("WorldPop Population Test - Kanpur")
print("="*80)
print(f"\nRaster file: {settings.POPULATION_RASTER_PATH}")
print(f"\nKanpur bounds:")
print(f"  Latitude:  {KANPUR_BOUNDS['min_lat']} to {KANPUR_BOUNDS['max_lat']}")
print(f"  Longitude: {KANPUR_BOUNDS['min_lon']} to {KANPUR_BOUNDS['max_lon']}")

# Get population
print("\nFetching population data from WorldPop...")
population = get_population_from_worldpop(
    KANPUR_BOUNDS,
    str(settings.POPULATION_RASTER_PATH)
)

# Calculate area
lat_range = KANPUR_BOUNDS['max_lat'] - KANPUR_BOUNDS['min_lat']
lon_range = KANPUR_BOUNDS['max_lon'] - KANPUR_BOUNDS['min_lon']
area_km2 = lat_range * 111.32 * lon_range * 111.32 * np.cos(np.radians((KANPUR_BOUNDS['min_lat'] + KANPUR_BOUNDS['max_lat']) / 2))

print(f"\n{'='*80}")
print(f"KANPUR POPULATION RESULTS")
print(f"{'='*80}")
print(f"\n  Total Population: {population:,} people")
print(f"  Area:            {area_km2:.2f} km²")
print(f"  Density:         {population/area_km2 if area_km2 > 0 else 0:,.0f} people/km²")
print(f"\n{'='*80}")

# Test smaller ward-sized areas
print("\n\nTesting smaller ward-sized areas:")
print("="*80)

# Ward 1: Central Kanpur
ward1_bounds = {
    'min_lat': 26.43,
    'max_lat': 26.48,
    'min_lon': 80.30,
    'max_lon': 80.35
}
pop1 = get_population_from_worldpop(ward1_bounds, str(settings.POPULATION_RASTER_PATH))
area1 = (ward1_bounds['max_lat'] - ward1_bounds['min_lat']) * 111.32 * \
        (ward1_bounds['max_lon'] - ward1_bounds['min_lon']) * 111.32 * \
        np.cos(np.radians((ward1_bounds['min_lat'] + ward1_bounds['max_lat']) / 2))

print(f"\nWard 1 (Central):")
print(f"  Bounds: {ward1_bounds}")
print(f"  Population: {pop1:,} people")
print(f"  Area: {area1:.2f} km²")
print(f"  Density: {pop1/area1 if area1 > 0 else 0:,.0f} people/km²")
print(f"  Daily Waste (0.5 kg/person): {pop1 * 0.5:,.0f} kg")
print(f"  Vehicles needed (1000 kg capacity): {np.ceil(pop1 * 0.5 / 1000):.0f}")

# Ward 2: East Kanpur
ward2_bounds = {
    'min_lat': 26.43,
    'max_lat': 26.48,
    'min_lon': 80.35,
    'max_lon': 80.40
}
pop2 = get_population_from_worldpop(ward2_bounds, str(settings.POPULATION_RASTER_PATH))
area2 = (ward2_bounds['max_lat'] - ward2_bounds['min_lat']) * 111.32 * \
        (ward2_bounds['max_lon'] - ward2_bounds['min_lon']) * 111.32 * \
        np.cos(np.radians((ward2_bounds['min_lat'] + ward2_bounds['max_lat']) / 2))

print(f"\nWard 2 (East):")
print(f"  Bounds: {ward2_bounds}")
print(f"  Population: {pop2:,} people")
print(f"  Area: {area2:.2f} km²")
print(f"  Density: {pop2/area2 if area2 > 0 else 0:,.0f} people/km²")
print(f"  Daily Waste (0.5 kg/person): {pop2 * 0.5:,.0f} kg")
print(f"  Vehicles needed (1000 kg capacity): {np.ceil(pop2 * 0.5 / 1000):.0f}")

print(f"\n{'='*80}")
print("Test completed! ✓")
print(f"{'='*80}\n")
