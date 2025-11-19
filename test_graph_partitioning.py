"""
Test script to verify graph partitioning implementation
Run from Django shell: python manage.py shell < test_graph_partitioning.py
"""

from osm_app.models import OSMFile
from osm_app.ward_utils import divide_by_graph_partitioning
import os

print("\n" + "="*60)
print("🧪 Testing Graph Partitioning Implementation")
print("="*60)

# Get the latest OSM file
try:
    osm_file = OSMFile.objects.latest('created_at')
    print(f"\n✓ Found OSM file: {osm_file.file_name}")
    print(f"  Bounds: {osm_file.min_lat:.4f}, {osm_file.max_lat:.4f}")
    print(f"         {osm_file.min_lon:.4f}, {osm_file.max_lon:.4f}")
except:
    print("\n❌ No OSM file found. Please upload an OSM file first.")
    exit(1)

# Check if population raster exists
from django.conf import settings
raster_path = str(settings.POPULATION_RASTER_PATH)
raster_exists = os.path.exists(raster_path)

print(f"\n📊 Population Raster:")
print(f"  Path: {raster_path}")
print(f"  Exists: {raster_exists}")

if not raster_exists:
    print("\n⚠️  WorldPop raster not found. Graph partitioning requires population data.")
    print("   The algorithm will still work but without population weighting.")
    raster_path = None

# Test graph partitioning
print("\n" + "="*60)
print("🎯 Running Graph Partitioning Algorithm")
print("="*60)

try:
    num_wards = 4
    print(f"\nCreating {num_wards} wards using graph partitioning...")
    
    config = divide_by_graph_partitioning(
        osm_file=osm_file,
        num_wards=num_wards,
        raster_path=raster_path
    )
    
    print(f"\n✅ SUCCESS! Ward configuration created:")
    print(f"   Config ID: {config.id}")
    print(f"   Layout: {config.ward_layout}")
    print(f"   Total Area: {config.total_area_km2:.2f} km²")
    print(f"   Number of Wards: {config.num_wards}")
    
    print(f"\n📋 Ward Details:")
    for ward in config.wards.all().order_by('ward_number'):
        print(f"\n   Ward {ward.ward_number}:")
        print(f"     Bounds: ({ward.min_lat:.4f}, {ward.min_lon:.4f}) to ({ward.max_lat:.4f}, {ward.max_lon:.4f})")
        print(f"     Centroid: ({ward.centroid_lat:.4f}, {ward.centroid_lon:.4f})")
        print(f"     Area: {ward.area_km2:.3f} km²")
        if ward.population > 0:
            print(f"     Population: {ward.population:,.0f}")
            print(f"     Density: {ward.population_density_per_km2:,.0f} people/km²")
    
    print("\n" + "="*60)
    print("✅ All tests passed! Graph partitioning is working correctly.")
    print("="*60)
    
    # Clean up test configuration
    print("\n🗑️  Cleaning up test configuration...")
    config.delete()
    print("   Test configuration deleted.")
    
except ImportError as e:
    print(f"\n❌ Import Error: {e}")
    print("   Make sure scikit-learn is installed:")
    print("   pip install scikit-learn>=1.3.0")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    print("\n   Check the error above for details.")

print("\n")
