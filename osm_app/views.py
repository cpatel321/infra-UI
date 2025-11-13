from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from .models import OSMFile
from .osm_utils import OSMProcessor
import os
import json


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
