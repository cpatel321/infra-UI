# Application Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     OSM Road Processor                       │
│                    Django Web Application                     │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   Backend    │────▶│   Storage    │
│  (HTML/JS)   │     │   (Django)   │     │   (Files)    │
└──────────────┘     └──────────────┘     └──────────────┘
     Leaflet.js         Python/XML           media/
     Bootstrap         OSMProcessor          db.sqlite3
```

## Application Flow

### 1. File Upload Flow
```
User → Upload Form → Django View → Validate .osm → Save to DB/Disk
                                         │
                                         ▼
                                  OSMFile Model
                                  (status: uploaded)
```

### 2. Processing Flow
```
User Clicks "Process"
         │
         ▼
   Load OSM File
         │
         ▼
   Parse XML (ElementTree)
         │
         ▼
   Filter Ways with highway tags
   (motorway, primary, residential, etc.)
         │
         ▼
   Collect referenced node IDs
         │
         ▼
   Keep only referenced nodes
         │
         ▼
   Remove all relations
         │
         ▼
   Save processed XML
         │
         ▼
   Update DB (status: processed)
```

### 3. Cropping Flow
```
User Opens Crop Page
         │
         ▼
   Load Processed File
         │
         ▼
   Convert to GeoJSON
         │
         ▼
   Display on Leaflet Map
         │
         ▼
   User Draws Rectangle
         │
         ▼
   Get Bounding Box Coords
   (min_lat, max_lat, min_lon, max_lon)
         │
         ▼
   Filter Nodes by Bounds
         │
         ▼
   Filter Ways with valid nodes
         │
         ▼
   Save Cropped File
         │
         ▼
   Update DB with new bounds
```

### 4. Download Flow
```
User Clicks "Download"
         │
         ▼
   Get processed_file path
         │
         ▼
   Create FileResponse
         │
         ▼
   Stream file to browser
         │
         ▼
   User saves .osm file
```

## Data Models

### OSMFile Model
```
┌─────────────────────────────────────┐
│           OSMFile                    │
├─────────────────────────────────────┤
│ id (PK)                             │
│ original_file (FileField)           │
│ processed_file (FileField)          │
│ file_name (CharField)               │
│ status (CharField)                  │
│   - uploaded                        │
│   - processing                      │
│   - processed                       │
│   - error                           │
│ uploaded_at (DateTime)              │
│ processed_at (DateTime)             │
│ min_lat, max_lat (Float)           │
│ min_lon, max_lon (Float)           │
└─────────────────────────────────────┘
```

## URL Structure

```
/                           → index view (upload form + file list)
/upload/                    → upload_file view (POST handler)
/process/<id>/              → process_file view (extract roads)
/crop/<id>/                 → crop_file view (interactive map)
/get-osm-data/<id>/        → get_osm_data view (GeoJSON API)
/download/<id>/             → download_file view (file download)
/admin/                     → Django admin panel
```

## File Structure

```
media/
└── osm_files/
    ├── original/           # Uploaded files
    │   └── map.osm
    └── processed/          # Processed files
        ├── processed_map.osm
        └── cropped_map.osm
```

## OSM XML Structure

### Before Processing
```xml
<osm>
  <node id="1" lat="40.7" lon="-74.0"/>
  <node id="2" lat="40.7" lon="-74.0"/>
  ...
  <way id="1">
    <nd ref="1"/>
    <nd ref="2"/>
    <tag k="highway" v="primary"/>     ← Roads (kept)
    <tag k="name" v="Main St"/>
  </way>
  <way id="2">
    <nd ref="3"/>
    <nd ref="4"/>
    <tag k="building" v="yes"/>         ← Buildings (removed)
  </way>
  <relation id="1">...</relation>       ← Relations (removed)
</osm>
```

### After Processing (Roads Only)
```xml
<osm>
  <node id="1" lat="40.7" lon="-74.0"/>  ← Only nodes used by roads
  <node id="2" lat="40.7" lon="-74.0"/>
  <way id="1">
    <nd ref="1"/>
    <nd ref="2"/>
    <tag k="highway" v="primary"/>       ← Only highway ways
    <tag k="name" v="Main St"/>
  </way>
</osm>
```

## OSMProcessor Class Methods

```python
class OSMProcessor:
    
    parse()
    # Parse OSM XML file using ElementTree
    
    filter_roads_only()
    # Remove non-road ways and unused nodes
    
    crop_to_bbox(min_lat, max_lat, min_lon, max_lon)
    # Filter to geographic bounding box
    
    save(output_file)
    # Save processed XML with pretty formatting
    
    get_bounds()
    # Calculate geographic bounds of data
    
    get_geojson()
    # Convert OSM data to GeoJSON for mapping
```

## Frontend Components

### Map Interface (Leaflet.js)
```javascript
// Initialize map
map = L.map('map')

// Add OSM tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/...')

// Display roads as GeoJSON
L.geoJSON(data, { style: {...} })

// Draw selection rectangle
map.on('mousedown/mousemove/mouseup')
L.rectangle([bounds])

// Send crop request
fetch('/crop/<id>/', { method: 'POST', body: JSON })
```

## Technology Stack

### Backend
- **Django 4.2**: Web framework
- **Python xml.etree.ElementTree**: XML parsing
- **xml.dom.minidom**: XML pretty printing
- **SQLite**: Database (default)

### Frontend
- **Bootstrap 5**: UI framework
- **Leaflet.js 1.9**: Interactive maps
- **Vanilla JavaScript**: Map interactions
- **OpenStreetMap**: Tile server

### Deployment
- Development server: `python manage.py runserver`
- Production: WSGI server (Gunicorn, uWSGI)
- Static files: WhiteNoise or web server

## Security Considerations

1. **File Validation**: Only .osm files accepted
2. **File Size Limits**: Configurable in settings.py
3. **CSRF Protection**: Django built-in
4. **File Storage**: Separate directories for original/processed
5. **Input Sanitization**: XML parser handles escaping

## Performance Notes

- **Small files (< 5MB)**: Process in seconds
- **Medium files (5-20MB)**: May take 10-30 seconds
- **Large files (> 20MB)**: Consider breaking into smaller areas
- **Memory usage**: Proportional to file size
- **Database**: File metadata only, not content

## Extension Ideas

- Add background task processing (Celery)
- Support multiple output formats (GeoJSON, KML)
- Add more filtering options (by road type)
- Implement user authentication
- Add file sharing capabilities
- Support for OSM PBF format
- Batch processing multiple files
- Export to various GIS formats
