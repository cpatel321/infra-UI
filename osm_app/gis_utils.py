"""
GIS utilities for working with geospatial data (population rasters, etc.)
"""
import os
import numpy as np


def get_population_from_worldpop(ward_bounds, raster_path):
    """
    Extract total population within ward bounds from WorldPop raster
    
    Args:
        ward_bounds: dict with keys min_lat, max_lat, min_lon, max_lon
        raster_path: path to WorldPop TIF file
    
    Returns:
        int: Estimated population count
    """
    try:
        import rasterio
        from rasterio.mask import mask
        from shapely.geometry import box
        
        # Open raster file
        with rasterio.open(raster_path) as src:
            # Create polygon from bounds (in lon, lat order for shapely)
            polygon = box(
                ward_bounds['min_lon'], 
                ward_bounds['min_lat'],
                ward_bounds['max_lon'], 
                ward_bounds['max_lat']
            )
            
            # Clip raster to polygon
            out_image, out_transform = mask(
                src, 
                [polygon], 
                crop=True,
                filled=True,
                nodata=0
            )
            
            # Sum all pixel values (excluding nodata)
            # WorldPop stores population count per pixel
            population = np.sum(out_image[out_image > 0])
            
            return int(round(population))
            
    except Exception as e:
        print(f"❌ Error reading population raster: {e}")
        return 0


def validate_raster_coverage(bounds, raster_path):
    """
    Check if raster covers the given bounds
    
    Args:
        bounds: dict with min_lat, max_lat, min_lon, max_lon
        raster_path: path to WorldPop TIF file
    
    Returns:
        dict: {
            'covered': True/False,
            'raster_bounds': (minx, miny, maxx, maxy),
            'message': 'explanation'
        }
    """
    try:
        import sys
        print(f"   DEBUG: Python executable: {sys.executable}")
        print(f"   DEBUG: sys.path: {sys.path[:3]}")  # First 3 paths
        
        import rasterio
        print(f"   DEBUG: rasterio imported successfully from {rasterio.__file__}")
        
        with rasterio.open(raster_path) as src:
            raster_bounds = src.bounds
            
            # Check if bounds are within raster extent
            covered = (
                bounds['min_lon'] >= raster_bounds.left and
                bounds['max_lon'] <= raster_bounds.right and
                bounds['min_lat'] >= raster_bounds.bottom and
                bounds['max_lat'] <= raster_bounds.top
            )
            
            return {
                'covered': covered,
                'raster_bounds': raster_bounds,
                'message': 'Area covered by raster' if covered else 'Area outside raster extent'
            }
    except ImportError as e:
        import sys
        print(f"   DEBUG: ImportError - Python: {sys.executable}")
        print(f"   DEBUG: ImportError details: {e}")
        return {
            'covered': False,
            'raster_bounds': None,
            'message': f'Error importing rasterio: {e}'
        }
    except Exception as e:
        return {
            'covered': False,
            'raster_bounds': None,
            'message': f'Error reading raster: {e}'
        }
