from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from .models import OSMFile, ComputationLog, WardConfiguration, Ward
from .osm_utils import OSMProcessor
from .routing_utils import OSMRoutePartitioner
from .ward_utils import (
    divide_area_into_wards, 
    divide_by_graph_partitioning,
    extract_ward_osm_data, 
    calculate_ward_statistics, 
    calculate_area_km2,
    validate_ward_before_routing,
    check_ward_connectivity,
    assign_wards_to_nearest_depot
)
import os
import json
import tempfile
import shutil
from django.conf import settings


def index(request):
    """Main page showing upload form and file list"""
    files = OSMFile.objects.all()
    return render(request, 'osm_app/index.html', {'files': files})


def use_default_map(request):
    """Load the default Kanpur map and process it"""
    try:
        # Path to default map
        default_map_path = os.path.join(settings.BASE_DIR, 'gis_data', 'population', 'default_map.osm')
        
        if not os.path.exists(default_map_path):
            messages.error(request, 'Default Kanpur map not found. Please upload a custom file.')
            return redirect('osm_app:index')
        
        # Create a database record
        osm_record = OSMFile.objects.create(
            file_name='Kanpur_Full_Map.osm',
            status='processing'
        )
        
        # Copy default file to media directory
        destination = os.path.join(settings.MEDIA_ROOT, 'osm_files', f'kanpur_full_{osm_record.id}.osm')
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(default_map_path, destination)
        
        # Update the record with file path
        osm_record.original_file.name = f'osm_files/kanpur_full_{osm_record.id}.osm'
        osm_record.save()
        
        # Process the file
        processor = OSMProcessor(destination)
        
        if not processor.parse():
            raise Exception("Failed to parse default OSM file")
        
        # Filter to roads only
        processor.filter_roads_only()
        
        # Get bounds for later use
        bounds = processor.get_bounds()
        if bounds:
            osm_record.min_lat = bounds['min_lat']
            osm_record.max_lat = bounds['max_lat']
            osm_record.min_lon = bounds['min_lon']
            osm_record.max_lon = bounds['max_lon']
        
        # Save processed file
        processed_path = os.path.join(settings.MEDIA_ROOT, 'osm_files', f'kanpur_processed_{osm_record.id}.osm')
        os.makedirs(os.path.dirname(processed_path), exist_ok=True)
        processor.save(processed_path)
        
        osm_record.processed_file.name = f'osm_files/kanpur_processed_{osm_record.id}.osm'
        osm_record.status = 'processed'
        osm_record.processed_at = timezone.now()
        
        osm_record.save()
        
        messages.success(request, 'Default Kanpur map loaded successfully! Now crop to your area of interest.')
        return redirect('osm_app:crop_file', file_id=osm_record.id)
        
    except Exception as e:
        messages.error(request, f'Error loading default map: {str(e)}')
        if 'osm_record' in locals():
            osm_record.delete()
        return redirect('osm_app:index')


def upload_file(request):
    """Handle OSM file upload"""
    if request.method == 'POST' and request.FILES.get('osm_file'):
        osm_file = request.FILES['osm_file']
        
        # Validate file extension
        if not osm_file.name.endswith('.osm'):
            messages.error(request, 'Please upload a valid .osm file')
            return redirect('osm_app:index')
        
        # Create database record
        osm_record = OSMFile.objects.create(
            original_file=osm_file,
            file_name=osm_file.name,
            status='uploaded'
        )
        
        messages.success(request, f'File "{osm_file.name}" uploaded successfully!')
        return redirect('osm_app:process_file', file_id=osm_record.id)
    
    return redirect('osm_app:index')


def process_file(request, file_id):
    """Process the OSM file to extract only roads"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if request.method == 'POST':
        try:
            osm_record.status = 'processing'
            osm_record.save()
            
            # Process the file
            processor = OSMProcessor(osm_record.original_file.path)
            
            if not processor.parse():
                raise Exception("Failed to parse OSM file")
            
            # Filter to roads only
            processor.filter_roads_only()
            
            # Get bounds for later use
            bounds = processor.get_bounds()
            if bounds:
                osm_record.min_lat = bounds['min_lat']
                osm_record.max_lat = bounds['max_lat']
                osm_record.min_lon = bounds['min_lon']
                osm_record.max_lon = bounds['max_lon']
            
            # Save processed file
            output_filename = f"processed_{osm_record.file_name}"
            output_path = os.path.join(
                os.path.dirname(osm_record.original_file.path),
                '../processed',
                output_filename
            )
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            processor.save(output_path)
            
            # Update record
            osm_record.processed_file.name = f'osm_files/processed/{output_filename}'
            osm_record.status = 'processed'
            osm_record.processed_at = timezone.now()
            osm_record.save()
            
            messages.success(request, 'File processed successfully! Roads extracted.')
            return redirect('osm_app:crop_file', file_id=osm_record.id)
            
        except Exception as e:
            osm_record.status = 'error'
            osm_record.save()
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('osm_app:index')
    
    return render(request, 'osm_app/process.html', {'osm_file': osm_record})


def crop_file(request, file_id):
    """Display map interface for cropping"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if request.method == 'POST':
        try:
            # Get bounding box from request
            data = json.loads(request.body)
            min_lat = float(data.get('min_lat'))
            max_lat = float(data.get('max_lat'))
            min_lon = float(data.get('min_lon'))
            max_lon = float(data.get('max_lon'))
            
            print(f"\n📍 Cropping to bbox: ({min_lat}, {min_lon}) to ({max_lat}, {max_lon})")
            
            # Process with new bounding box
            processor = OSMProcessor(osm_record.processed_file.path)
            
            if not processor.parse():
                raise Exception("Failed to parse processed file")
            
            # Count nodes and ways before cropping
            nodes_before = len(processor.root.findall('node'))
            ways_before = len(processor.root.findall('way'))
            print(f"   Before crop: {nodes_before} nodes, {ways_before} ways")
            
            processor.crop_to_bbox(min_lat, max_lat, min_lon, max_lon)
            
            # Count nodes and ways after cropping
            nodes_after = len(processor.root.findall('node'))
            ways_after = len(processor.root.findall('way'))
            print(f"   After crop: {nodes_after} nodes, {ways_after} ways")
            
            # Save cropped file - determine correct path
            base_filename = os.path.basename(osm_record.file_name)
            output_filename = f"cropped_{base_filename}"
            
            # Save in the same directory structure as the processed file
            if osm_record.processed_file:
                processed_dir = os.path.dirname(osm_record.processed_file.path)
                output_path = os.path.join(processed_dir, output_filename)
                
                # Get relative path for database storage
                media_root = os.path.join(settings.MEDIA_ROOT, 'osm_files')
                if processed_dir.startswith(media_root):
                    relative_dir = os.path.relpath(processed_dir, media_root)
                    if relative_dir == '.':
                        db_path = f'osm_files/{output_filename}'
                    else:
                        db_path = f'osm_files/{relative_dir}/{output_filename}'
                else:
                    db_path = f'osm_files/{output_filename}'
            else:
                # Fallback: save to osm_files root
                output_path = os.path.join(settings.MEDIA_ROOT, 'osm_files', output_filename)
                db_path = f'osm_files/{output_filename}'
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            print(f"   Saving to: {output_path}")
            processor.save(output_path)
            print(f"   File saved successfully")
            
            # Update record
            osm_record.processed_file.name = db_path
            osm_record.min_lat = min_lat
            osm_record.max_lat = max_lat
            osm_record.min_lon = min_lon
            osm_record.max_lon = max_lon
            osm_record.save()
            
            print(f"   Database updated: {db_path}")
            print(f"   ✅ Crop completed successfully\n")
            
            return JsonResponse({'success': True, 'message': 'File cropped successfully!'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # Calculate bounds
    bounds = {
        'min_lat': osm_record.min_lat,
        'max_lat': osm_record.max_lat,
        'min_lon': osm_record.min_lon,
        'max_lon': osm_record.max_lon
    }
    
    return render(request, 'osm_app/crop.html', {
        'osm_file': osm_record,
        'bounds': bounds
    })


def get_osm_data(request, file_id):
    """Get OSM data as GeoJSON for map display"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    try:
        file_path = osm_record.processed_file.path if osm_record.processed_file else osm_record.original_file.path
        
        processor = OSMProcessor(file_path)
        if not processor.parse():
            return JsonResponse({'error': 'Failed to parse file'}, status=400)
        
        geojson = processor.get_geojson()
        bounds = processor.get_bounds()
        
        return JsonResponse({
            'geojson': geojson,
            'bounds': bounds
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def download_file(request, file_id):
    """Download the processed OSM file"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if not osm_record.processed_file:
        messages.error(request, 'No processed file available')
        return redirect('osm_app:index')
    
    try:
        file_path = osm_record.processed_file.path
        response = FileResponse(
            open(file_path, 'rb'),
            content_type='application/xml'
        )
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
    except Exception as e:
        messages.error(request, f'Error downloading file: {str(e)}')
        return redirect('osm_app:index')


def route_planning(request, file_id):
    """Display route planning page with map and vehicle input"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if not osm_record.processed_file:
        messages.error(request, 'No processed file available for route planning')
        return redirect('osm_app:index')
    
    # Calculate bounds
    bounds = {
        'min_lat': osm_record.min_lat,
        'max_lat': osm_record.max_lat,
        'min_lon': osm_record.min_lon,
        'max_lon': osm_record.max_lon
    }
    
    # Get statistics
    try:
        partitioner = OSMRoutePartitioner(osm_record.processed_file.path)
        partitioner.parse_osm()
        partitioner.build_graph()
        partitioner.find_centroid_depot()
        partitioner.get_connected_component()
        stats = partitioner.get_statistics()
    except Exception as e:
        stats = {}
        print(f"Error getting statistics: {e}")
    
    return render(request, 'osm_app/route_planning.html', {
        'osm_file': osm_record,
        'bounds': bounds,
        'stats': stats
    })


def compute_routes(request, file_id):
    """Compute optimal routes for k vehicles (single ward/normal mode)"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            k = int(data.get('k', 1))
            
            if k < 1:
                return JsonResponse({'success': False, 'error': 'Number of vehicles must be at least 1'})
            
            # Use modular function
            result = compute_single_ward_routes(
                osm_file_path=osm_record.processed_file.path,
                num_vehicles=k,
                bounds=None,  # No bounds - use entire file
                ward_label="Full Area"
            )
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'routes': result['routes'],
                    'stats': result['stats']
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                })
            
        except Exception as e:
            print(f"Error computing routes: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def log_computation(request):
    """Log computation performance metrics"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            osm_record = get_object_or_404(OSMFile, id=data.get('file_id'))
            
            ComputationLog.objects.create(
                osm_file=osm_record,
                num_vehicles=data.get('num_vehicles'),
                computation_time=data.get('computation_time'),
                total_length_m=data.get('total_length', 0),
                total_nodes=data.get('total_nodes', 0),
                total_roads=data.get('total_roads', 0)
            )
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            print(f"Error logging computation: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def ward_config(request, file_id):
    """Display ward configuration page - intermediate page between crop and route planning"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if not osm_record.processed_file:
        messages.error(request, 'No processed file available')
        return redirect('osm_app:index')
    
    # Calculate total area
    total_area_km2 = calculate_area_km2(
        osm_record.min_lat, osm_record.max_lat,
        osm_record.min_lon, osm_record.max_lon
    )
    
    return render(request, 'osm_app/ward_config.html', {
        'osm_file': osm_record,
        'total_area_km2': total_area_km2
    })


def create_ward_config(request, file_id):
    """Create ward configuration and divide area into wards"""
    from django.conf import settings
    from .gis_utils import get_population_from_worldpop, validate_raster_coverage
    
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            num_wards = int(data.get('num_wards', 4))
            ward_layout = data.get('ward_layout', 'auto_grid')
            
            # Get waste parameters
            use_worldpop = data.get('use_worldpop', True)
            waste_per_capita = float(data.get('waste_per_capita', 0.5))
            vehicle_capacity = float(data.get('vehicle_capacity', 1000.0))
            
            print(f"\n{'='*80}")
            print(f"Ward Configuration Request:")
            print(f"  Num Wards: {num_wards}")
            print(f"  Use WorldPop: {use_worldpop}")
            print(f"  Waste per Capita: {waste_per_capita} kg/day")
            print(f"  Vehicle Capacity: {vehicle_capacity} kg")
            print(f"{'='*80}\n")
            
            if num_wards < 2 or num_wards > 100:
                return JsonResponse({'success': False, 'error': 'Number of wards must be between 2 and 100'})
            
            # Check if WorldPop raster is available
            raster_available = False
            if use_worldpop:
                print(f"📂 Checking WorldPop raster...")
                print(f"   Path: {settings.POPULATION_RASTER_PATH}")
                print(f"   Exists: {settings.POPULATION_RASTER_PATH.exists()}")
                
                if settings.POPULATION_RASTER_PATH.exists():
                    bounds = {
                        'min_lat': osm_record.min_lat,
                        'max_lat': osm_record.max_lat,
                        'min_lon': osm_record.min_lon,
                        'max_lon': osm_record.max_lon
                    }
                    print(f"   OSM File Bounds: {bounds}")
                    coverage = validate_raster_coverage(bounds, str(settings.POPULATION_RASTER_PATH))
                    print(f"   Coverage Check: {coverage}")
                    raster_available = coverage['covered']
                    if not raster_available:
                        print(f"   ⚠️  Area outside raster coverage: {coverage['message']}")
                    else:
                        print(f"   ✅ Area is covered by raster")
                else:
                    print(f"   ❌ Raster file not found!")
            else:
                print(f"⚠️  WorldPop disabled by user")
            
            # Create ward configuration
            # Use graph partitioning if available, otherwise population-balanced or grid
            use_graph_partitioning = data.get('use_graph_partitioning', False)
            
            if use_graph_partitioning and raster_available:
                print(f"\n🎯 Using GRAPH PARTITIONING ward division (Advanced)")
                print(f"   (Respects road network topology, no split roads)")
                try:
                    config = divide_by_graph_partitioning(
                        osm_record, 
                        num_wards, 
                        str(settings.POPULATION_RASTER_PATH)
                    )
                except Exception as e:
                    print(f"   ⚠️  Graph partitioning failed: {e}")
                    print(f"   📐 Falling back to grid-based division")
                    config = divide_area_into_wards(osm_record, num_wards, ward_layout)
            else:
                print(f"\n📐 Using GRID-BASED ward division")
                print(f"   (Creates equal geographic area per ward)")
                config = divide_area_into_wards(osm_record, num_wards, ward_layout)
            
            wards_data = []
            
            # Calculate statistics and population for each ward
            for ward in config.wards.all():
                try:
                    # Set waste parameters
                    ward.waste_per_capita_kg = waste_per_capita
                    ward.vehicle_capacity_kg = vehicle_capacity
                    
                    # Extract OSM data for this ward
                    ward_osm_xml = extract_ward_osm_data(osm_record.processed_file.path, ward)
                    
                    # Calculate statistics
                    calculate_ward_statistics(ward_osm_xml, ward)
                    
                    # Validate ward data quality
                    print(f"   🔍 Validating ward {ward.ward_number}...")
                    validation_result = validate_ward_before_routing(ward)
                    if validation_result['warnings']:
                        for warning in validation_result['warnings']:
                            print(f"      ⚠️  {warning}")
                    
                    # Check connectivity
                    connectivity_result = check_ward_connectivity(ward_osm_xml, ward)
                    if not connectivity_result['connected']:
                        print(f"      ⚠️  {connectivity_result['message']}")
                    
                    # Get population from WorldPop if available
                    if raster_available:
                        print(f"   📍 Fetching population from WorldPop for Ward {ward.ward_number}...")
                        ward_bounds = {
                            'min_lat': ward.min_lat,
                            'max_lat': ward.max_lat,
                            'min_lon': ward.min_lon,
                            'max_lon': ward.max_lon
                        }
                        print(f"      Ward bounds: {ward_bounds}")
                        population = get_population_from_worldpop(
                            ward_bounds,
                            str(settings.POPULATION_RASTER_PATH)
                        )
                        print(f"      Raw population result: {population}")
                        ward.population = population
                        ward.population_source = 'worldpop'
                        ward.population_density_per_km2 = population / ward.area_km2 if ward.area_km2 > 0 else 0
                        ward.save()
                        print(f"   ✅ Population: {population:,} people (Density: {ward.population_density_per_km2:.0f}/km²)")
                    else:
                        ward.population = 0
                        ward.population_source = 'manual'
                        ward.save()
                        print(f"   ⚠️  WorldPop not available, population set to 0 (raster_available={raster_available})")
                    
                    wards_data.append({
                        'ward_number': ward.ward_number,
                        'population': ward.population,
                        'area_km2': ward.area_km2,
                        'density': ward.population_density_per_km2,
                        'roads': ward.total_roads,
                        'length_m': ward.total_length_m
                    })
                    
                except Exception as e:
                    print(f"Error processing ward {ward.ward_number}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Assign wards to nearest depots if any exist
            print(f"\n📍 Checking for depot assignments...")
            depot_result = assign_wards_to_nearest_depot(config)
            if depot_result['success']:
                print(f"   ✅ Assigned {depot_result['assigned_wards']} wards to depots")
                for assignment in depot_result['assignments']:
                    print(f"      Ward {assignment['ward']} → {assignment['depot']} ({assignment['distance_km']:.1f} km)")
            else:
                print(f"   ⚠️  {depot_result['message']}")
            
            return JsonResponse({
                'success': True,
                'config_id': config.id,
                'wards': wards_data,
                'population_source': 'worldpop' if raster_available else 'manual'
            })
            
        except Exception as e:
            print(f"Error creating ward configuration: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def multiward_routing(request, file_id):
    """Display multi-ward routing page with map and per-ward vehicle controls"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    config_id = request.GET.get('config_id')
    if not config_id:
        messages.error(request, 'No ward configuration specified')
        return redirect('osm_app:ward_config', file_id=file_id)
    
    config = get_object_or_404(WardConfiguration, id=config_id, osm_file=osm_record)
    wards = list(config.wards.all())
    
    # Prepare ward data for JavaScript
    wards_data = []
    for ward in wards:
        wards_data.append({
            'id': ward.id,
            'ward_number': ward.ward_number,
            'min_lat': ward.min_lat,
            'max_lat': ward.max_lat,
            'min_lon': ward.min_lon,
            'max_lon': ward.max_lon,
            'centroid_lat': ward.centroid_lat,
            'centroid_lon': ward.centroid_lon,
            'area_km2': ward.area_km2,
            'total_nodes': ward.total_nodes,
            'total_roads': ward.total_roads,
            'total_length_m': ward.total_length_m,
            'population': ward.population,
            'population_density_per_km2': ward.population_density_per_km2,
            'waste_per_capita_kg': ward.waste_per_capita_kg,
            'vehicle_capacity_kg': ward.vehicle_capacity_kg,
            'validation_warnings': ward.validation_warnings,
            'has_valid_data': ward.has_valid_data,
            'is_connected': ward.is_connected,
            'assigned_depot': ward.assigned_depot.name if ward.assigned_depot else None,
            'depot_distance_km': ward.depot_distance_km
        })
    
    return render(request, 'osm_app/multiward_routing.html', {
        'osm_file': osm_record,
        'config': config,
        'wards': wards,
        'wards_json': json.dumps(wards_data)
    })
    
    return render(request, 'osm_app/multiward_routing.html', {
        'osm_file': osm_record,
        'config': config,
        'wards_json': json.dumps(wards_data)
    })


def compute_single_ward_routes(osm_file_path, num_vehicles, bounds=None, ward_label="Area"):
    """
    Modular function to compute routes for a single area/ward.
    Can be called directly or via API.
    
    Args:
        osm_file_path: Path to OSM file (can be full file or ward-cropped file)
        num_vehicles: Number of vehicles to use
        bounds: Optional dict with min_lat, max_lat, min_lon, max_lon (for cropping)
        ward_label: Label for logging (e.g., "Ward 2" or "Main Area")
    
    Returns:
        dict with success, routes (GeoJSON), computation_time, stats
    """
    import time
    
    print(f"\n{'='*80}")
    print(f"🔄 Computing routes for {ward_label}")
    print(f"   Vehicles: {num_vehicles}")
    if bounds:
        print(f"   Bounds: ({bounds['min_lat']:.6f}, {bounds['min_lon']:.6f}) to ({bounds['max_lat']:.6f}, {bounds['max_lon']:.6f})")
    print(f"{'='*80}\n")
    
    try:
        # If bounds provided, create cropped temporary file
        working_file_path = osm_file_path
        temp_file_created = False
        
        if bounds:
            print(f"📊 Extracting area data with bounds...")
            # Read original file and extract bounded area
            import xml.etree.ElementTree as ET
            tree = ET.parse(osm_file_path)
            root = tree.getroot()
            
            # Create new OSM with bounds
            osm_root = ET.Element('osm', version='0.6', generator='WardExtractor')
            ET.SubElement(osm_root, 'bounds',
                         minlat=str(bounds['min_lat']),
                         minlon=str(bounds['min_lon']),
                         maxlat=str(bounds['max_lat']),
                         maxlon=str(bounds['max_lon']))
            
            # Collect nodes in bounds
            bounded_nodes = {}
            for node in root.findall('node'):
                lat = float(node.get('lat'))
                lon = float(node.get('lon'))
                if (bounds['min_lat'] <= lat <= bounds['max_lat'] and 
                    bounds['min_lon'] <= lon <= bounds['max_lon']):
                    bounded_nodes[node.get('id')] = node
            
            print(f"   ✓ Found {len(bounded_nodes)} nodes in bounds")
            
            # Collect ways with nodes in bounds
            bounded_ways = []
            referenced_nodes = set()
            for way in root.findall('way'):
                way_nodes = [nd.get('ref') for nd in way.findall('nd')]
                if any(nd_ref in bounded_nodes for nd_ref in way_nodes):
                    bounded_ways.append(way)
                    referenced_nodes.update(way_nodes)
            
            print(f"   ✓ Found {len(bounded_ways)} ways in bounds")
            
            if not bounded_ways:
                return {
                    'success': False,
                    'error': f'{ward_label} has no roads in the selected area',
                    'routes': None,
                    'computation_time': 0,
                    'stats': {}
                }
            
            # Add all referenced nodes and ways
            for node in root.findall('node'):
                if node.get('id') in referenced_nodes:
                    osm_root.append(node)
            for way in bounded_ways:
                osm_root.append(way)
            
            # Create temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(ET.tostring(osm_root, encoding='unicode'))
                working_file_path = tmp_file.name
                temp_file_created = True
            print(f"   ✓ Created temporary bounded file")
        
        # Run routing algorithm
        start_time = time.time()
        
        print(f"🚗 Initializing route partitioner...")
        partitioner = OSMRoutePartitioner(working_file_path)
        
        print(f"🗺️  Computing routes for {num_vehicles} vehicle(s)...")
        routes_geojson = partitioner.compute_routes(num_vehicles)
        
        computation_time = time.time() - start_time
        
        # Get statistics
        stats = partitioner.get_statistics()
        
        print(f"✓ Routes computed successfully!")
        print(f"   Computation time: {computation_time:.2f} seconds")
        print(f"   Routes generated: {len(routes_geojson.get('features', []))} routes")
        print(f"{'='*80}\n")
        
        # Cleanup temporary file if created
        if temp_file_created and os.path.exists(working_file_path):
            os.unlink(working_file_path)
        
        return {
            'success': True,
            'routes': routes_geojson,
            'computation_time': computation_time,
            'stats': stats
        }
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ ERROR in {ward_label}")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        print(f"{'='*80}")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        
        # Cleanup on error
        if temp_file_created and 'working_file_path' in locals() and os.path.exists(working_file_path):
            os.unlink(working_file_path)
        
        return {
            'success': False,
            'error': str(e),
            'routes': None,
            'computation_time': 0,
            'stats': {}
        }


def compute_ward_route(request, file_id):
    """API endpoint to compute routes for a specific ward"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ward_id = data.get('ward_id')
            num_vehicles = int(data.get('num_vehicles', 1))
            
            ward = get_object_or_404(Ward, id=ward_id)
            
            # Extract ward OSM data using centroid-based assignment (prevents overlap)
            print(f"\n{'='*80}")
            print(f"🔄 Computing routes for Ward {ward.ward_number}")
            print(f"   Using centroid-based road assignment (no overlap)")
            print(f"{'='*80}\n")
            
            ward_osm_xml = extract_ward_osm_data(osm_record.processed_file.path, ward)
            
            # Create temporary file with ward-specific OSM data
            import tempfile
            import time
            with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(ward_osm_xml)
                temp_file_path = tmp_file.name
            
            try:
                # Run routing algorithm on ward-specific data
                start_time = time.time()
                
                print(f"🚗 Initializing route partitioner...")
                from .routing_utils import OSMRoutePartitioner
                partitioner = OSMRoutePartitioner(temp_file_path)
                
                print(f"🗺️  Computing routes for {num_vehicles} vehicle(s)...")
                routes_geojson = partitioner.compute_routes(num_vehicles)
                
                computation_time = time.time() - start_time
                
                # Get statistics
                stats = partitioner.get_statistics()
                
                print(f"✓ Routes computed successfully!")
                print(f"   Computation time: {computation_time:.2f} seconds")
                print(f"   Routes generated: {len(routes_geojson.get('features', []))} routes")
                print(f"{'='*80}\n")
                
                # Update ward with results
                ward.num_vehicles = num_vehicles
                ward.routes_geojson = routes_geojson
                ward.computation_time = computation_time
                ward.computed_at = timezone.now()
                
                # Update statistics
                if stats:
                    ward.total_nodes = stats.get('total_nodes', 0)
                    ward.total_roads = stats.get('total_roads', 0)
                    ward.total_length_m = stats.get('total_length_m', 0)
                
                ward.save()
                
                return JsonResponse({
                    'success': True,
                    'routes': routes_geojson,
                    'computation_time': computation_time
                })
                
            finally:
                # Cleanup temporary file
                import os
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            print(f"❌ API Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
