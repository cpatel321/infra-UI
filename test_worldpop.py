"""
Test script to visualize WorldPop population density for Kanpur region

SETUP:
Run this first: pip install rasterio matplotlib

Then run: python test_worldpop.py
"""

try:
    import rasterio
    from rasterio.plot import show
    import matplotlib.pyplot as plt
    from rasterio.mask import mask
    from shapely.geometry import box
    import numpy as np
except ImportError as e:
    print("="*80)
    print("ERROR: Required packages not installed")
    print("="*80)
    print(f"\nMissing: {e}")
    print("\nPlease run:")
    print("  pip install rasterio matplotlib")
    print("\nThen run this script again.")
    print("="*80)
    exit(1)

# WorldPop TIF file path
RASTER_PATH = r'C:\Users\chand\Desktop\infra-UI\gis_data\population\ind_ppp_2020.tif'

# Kanpur approximate bounds (can be adjusted)
# These are rough coordinates covering Kanpur city
KANPUR_BOUNDS = {
    'min_lat': 26.35,   # South
    'max_lat': 26.55,   # North
    'min_lon': 80.25,   # West
    'max_lon': 80.45    # East
}

def test_worldpop_kanpur():
    """Extract and visualize population data for Kanpur"""
    
    print("="*80)
    print("WorldPop Population Density Test - Kanpur")
    print("="*80)
    print(f"\nRaster file: {RASTER_PATH}")
    print(f"\nKanpur bounds:")
    print(f"  Latitude:  {KANPUR_BOUNDS['min_lat']} to {KANPUR_BOUNDS['max_lat']}")
    print(f"  Longitude: {KANPUR_BOUNDS['min_lon']} to {KANPUR_BOUNDS['max_lon']}")
    print()
    
    try:
        # Open raster
        print("Opening WorldPop raster file...")
        with rasterio.open(RASTER_PATH) as src:
            # Print raster metadata
            print(f"✓ Raster opened successfully")
            print(f"\nRaster Information:")
            print(f"  CRS: {src.crs}")
            print(f"  Resolution: {src.res}")
            print(f"  Bounds: {src.bounds}")
            print(f"  Width x Height: {src.width} x {src.height}")
            print(f"  Data type: {src.dtypes[0]}")
            
            # Create polygon for Kanpur
            polygon = box(
                KANPUR_BOUNDS['min_lon'],
                KANPUR_BOUNDS['min_lat'],
                KANPUR_BOUNDS['max_lon'],
                KANPUR_BOUNDS['max_lat']
            )
            
            # Check if Kanpur is within raster bounds
            raster_bounds = src.bounds
            in_bounds = (
                KANPUR_BOUNDS['min_lon'] >= raster_bounds.left and
                KANPUR_BOUNDS['max_lon'] <= raster_bounds.right and
                KANPUR_BOUNDS['min_lat'] >= raster_bounds.bottom and
                KANPUR_BOUNDS['max_lat'] <= raster_bounds.top
            )
            
            if not in_bounds:
                print("\n⚠️  WARNING: Kanpur bounds are outside raster extent!")
                print(f"   Raster covers: {raster_bounds}")
                return
            
            print(f"\n✓ Kanpur is within raster coverage")
            
            # Clip raster to Kanpur bounds
            print(f"\nClipping raster to Kanpur region...")
            out_image, out_transform = mask(
                src,
                [polygon],
                crop=True,
                filled=True,
                nodata=0
            )
            
            # Calculate statistics
            population_data = out_image[0]
            population_data_valid = population_data[population_data > 0]
            
            total_population = np.sum(population_data_valid)
            mean_density = np.mean(population_data_valid) if len(population_data_valid) > 0 else 0
            max_density = np.max(population_data_valid) if len(population_data_valid) > 0 else 0
            num_pixels = len(population_data_valid)
            
            print(f"\n{'='*80}")
            print(f"KANPUR POPULATION STATISTICS")
            print(f"{'='*80}")
            print(f"\n  Total Population: {total_population:,.0f} people")
            print(f"  Mean Density:     {mean_density:.2f} people/pixel")
            print(f"  Max Density:      {max_density:.2f} people/pixel")
            print(f"  Populated Pixels: {num_pixels:,}")
            print(f"  Resolution:       ~1km x 1km per pixel")
            print(f"\n{'='*80}")
            
            # Create visualization
            print(f"\nGenerating visualization...")
            
            fig, axes = plt.subplots(1, 2, figsize=(16, 6))
            
            # Plot 1: Population density map
            im1 = axes[0].imshow(
                population_data,
                cmap='YlOrRd',
                interpolation='nearest'
            )
            axes[0].set_title(f'Kanpur Population Density\nTotal: {total_population:,.0f} people', 
                            fontsize=14, fontweight='bold')
            axes[0].set_xlabel('Longitude →', fontsize=11)
            axes[0].set_ylabel('Latitude →', fontsize=11)
            axes[0].grid(True, alpha=0.3)
            plt.colorbar(im1, ax=axes[0], label='People per pixel (~1km²)')
            
            # Plot 2: Histogram
            if len(population_data_valid) > 0:
                axes[1].hist(population_data_valid, bins=50, color='steelblue', edgecolor='black', alpha=0.7)
                axes[1].set_title('Population Density Distribution', fontsize=14, fontweight='bold')
                axes[1].set_xlabel('People per pixel', fontsize=11)
                axes[1].set_ylabel('Frequency', fontsize=11)
                axes[1].axvline(mean_density, color='red', linestyle='--', linewidth=2, 
                              label=f'Mean: {mean_density:.0f}')
                axes[1].legend()
                axes[1].grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            
            # Save figure
            output_file = 'kanpur_population_worldpop.png'
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            print(f"✓ Visualization saved: {output_file}")
            
            # Show plot
            plt.show()
            
            print(f"\n{'='*80}")
            print("Test completed successfully! ✓")
            print(f"{'='*80}\n")
            
    except FileNotFoundError:
        print(f"\n❌ ERROR: Raster file not found at {RASTER_PATH}")
        print("   Please check the file path.")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


def test_custom_area(min_lat, max_lat, min_lon, max_lon):
    """Test population for any custom area"""
    
    print(f"\nTesting custom area:")
    print(f"  Lat: {min_lat} to {max_lat}")
    print(f"  Lon: {min_lon} to {max_lon}")
    
    try:
        with rasterio.open(RASTER_PATH) as src:
            polygon = box(min_lon, min_lat, max_lon, max_lat)
            out_image, out_transform = mask(src, [polygon], crop=True, filled=True, nodata=0)
            
            population = np.sum(out_image[out_image > 0])
            area_km2 = (max_lat - min_lat) * 111.32 * (max_lon - min_lon) * 111.32 * np.cos(np.radians((min_lat + max_lat) / 2))
            
            print(f"\n  Total Population: {population:,.0f} people")
            print(f"  Area: {area_km2:.2f} km²")
            print(f"  Density: {population/area_km2:.0f} people/km²")
            
            return population
            
    except Exception as e:
        print(f"  Error: {e}")
        return 0


if __name__ == '__main__':
    # Run main test for Kanpur
    test_worldpop_kanpur()
    
    # Uncomment below to test other areas
    # print("\n" + "="*80)
    # print("Testing smaller ward-sized area:")
    # print("="*80)
    # test_custom_area(26.42, 26.44, 80.30, 80.32)
