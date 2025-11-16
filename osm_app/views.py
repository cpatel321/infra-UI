from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from .models import OSMFile, ComputationLog, WardConfiguration, Ward
from .osm_utils import OSMProcessor
from .routing_utils import OSMRoutePartitioner
from .ward_utils import divide_area_into_wards, extract_ward_osm_data, calculate_ward_statistics, calculate_area_km2
import os
import json
import tempfile


def index(request):
    """Main page showing upload form and file list"""
    files = OSMFile.objects.all()
    return render(request, 'osm_app/index.html', {'files': files})


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
            
            # Process with new bounding box
            processor = OSMProcessor(osm_record.processed_file.path)
            
            if not processor.parse():
                raise Exception("Failed to parse processed file")
            
            processor.crop_to_bbox(min_lat, max_lat, min_lon, max_lon)
            
            # Save cropped file
            output_filename = f"cropped_{osm_record.file_name}"
            output_path = os.path.join(
                os.path.dirname(osm_record.processed_file.path),
                output_filename
            )
            
            processor.save(output_path)
            
            # Update record
            osm_record.processed_file.name = f'osm_files/processed/{output_filename}'
            osm_record.min_lat = min_lat
            osm_record.max_lat = max_lat
            osm_record.min_lon = min_lon
            osm_record.max_lon = max_lon
            osm_record.save()
            
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
    """Compute optimal routes for k vehicles"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            k = int(data.get('k', 1))
            
            if k < 1:
                return JsonResponse({'success': False, 'error': 'Number of vehicles must be at least 1'})
            
            # Run routing algorithm
            partitioner = OSMRoutePartitioner(osm_record.processed_file.path)
            routes_geojson = partitioner.compute_routes(k)
            
            # Get statistics
            stats = partitioner.get_statistics()
            
            return JsonResponse({
                'success': True,
                'routes': routes_geojson,
                'stats': stats
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
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            num_wards = int(data.get('num_wards', 4))
            ward_layout = data.get('ward_layout', 'auto_grid')
            
            if num_wards < 2 or num_wards > 100:
                return JsonResponse({'success': False, 'error': 'Number of wards must be between 2 and 100'})
            
            # Create ward configuration
            config = divide_area_into_wards(osm_record, num_wards, ward_layout)
            
            # Calculate statistics for each ward
            for ward in config.wards.all():
                try:
                    # Extract OSM data for this ward
                    ward_osm_xml = extract_ward_osm_data(osm_record.processed_file.path, ward)
                    
                    # Calculate statistics
                    calculate_ward_statistics(ward_osm_xml, ward)
                except Exception as e:
                    print(f"Error calculating statistics for ward {ward.ward_number}: {e}")
            
            return JsonResponse({
                'success': True,
                'config_id': config.id
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
            'total_length_m': ward.total_length_m
        })
    
    return render(request, 'osm_app/multiward_routing.html', {
        'osm_file': osm_record,
        'config': config,
        'wards_json': json.dumps(wards_data)
    })


def compute_ward_route(request, file_id):
    """Compute optimal routes for a specific ward"""
    osm_record = get_object_or_404(OSMFile, id=file_id)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ward_id = data.get('ward_id')
            num_vehicles = int(data.get('num_vehicles', 1))
            
            ward = get_object_or_404(Ward, id=ward_id)
            
            # Extract OSM data for this ward
            ward_osm_xml = extract_ward_osm_data(osm_record.processed_file.path, ward)
            
            # Create temporary file for ward OSM data
            with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as tmp_file:
                tmp_file.write(ward_osm_xml)
                tmp_file_path = tmp_file.name
            
            try:
                # Run routing algorithm on ward
                import time
                start_time = time.time()
                
                partitioner = OSMRoutePartitioner(tmp_file_path)
                routes_geojson = partitioner.compute_routes(num_vehicles)
                
                computation_time = time.time() - start_time
                
                # Update ward with results
                ward.num_vehicles = num_vehicles
                ward.routes_geojson = routes_geojson
                ward.computation_time = computation_time
                ward.computed_at = timezone.now()
                ward.save()
                
                return JsonResponse({
                    'success': True,
                    'routes': routes_geojson,
                    'computation_time': computation_time
                })
                
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
            
        except Exception as e:
            print(f"Error computing ward route: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
