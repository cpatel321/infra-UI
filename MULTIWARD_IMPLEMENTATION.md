# Multi-Ward Route Planning Implementation

## Overview
Implemented a comprehensive multi-ward routing system to handle large area route planning efficiently. The system divides large areas into smaller wards that can be processed independently, significantly reducing computation time for large datasets.

## Implementation Summary

### 1. New Database Models (`osm_app/models.py`)

#### WardConfiguration Model
- Stores configuration for dividing an area into multiple wards
- Fields:
  - `osm_file`: ForeignKey to parent OSM file
  - `num_wards`: Number of wards to create (default: 4)
  - `total_area_km2`: Total area in square kilometers
  - `area_per_ward_km2`: Average area per ward
  - `ward_layout`: Layout strategy (auto_grid, manual)
  - `grid_rows`, `grid_cols`: Grid dimensions
  - `ward_dimensions_km`: Approximate dimensions string
  - `created_at`: Timestamp

#### Ward Model
- Represents individual ward within a configuration
- Fields:
  - `config`: ForeignKey to WardConfiguration
  - `ward_number`: Ward identifier (1, 2, 3, ...)
  - Bounding box: `min_lat`, `max_lat`, `min_lon`, `max_lon`
  - Centroid: `centroid_lat`, `centroid_lon` (depot location)
  - Statistics: `area_km2`, `total_nodes`, `total_roads`, `total_length_m`
  - Routing results: `num_vehicles`, `routes_geojson`, `computation_time`, `computed_at`

### 2. Ward Division Utilities (`osm_app/ward_utils.py`)

#### Key Functions:
- **`haversine_distance()`**: Calculate distance between two points on Earth
- **`calculate_area_km2()`**: Calculate bounding box area in square kilometers
- **`calculate_optimal_grid()`**: Determine optimal grid layout (rows × cols)
- **`divide_area_into_wards()`**: Main function to create ward configuration and divide area
- **`extract_ward_osm_data()`**: Extract OSM data for a specific ward from full file
- **`calculate_ward_statistics()`**: Calculate statistics (nodes, roads, length) for a ward

### 3. Views (`osm_app/views.py`)

#### New Views:
- **`ward_config(file_id)`**: Display intermediate page with routing approach selection
- **`create_ward_config(file_id)`**: Create ward configuration via AJAX
- **`multiward_routing(file_id)`**: Display multi-ward routing page with map
- **`compute_ward_route(file_id)`**: Compute routes for a specific ward via AJAX

### 4. Templates

#### `templates/osm_app/ward_config.html`
Intermediate page between crop and route planning:
- Two card-based options: Single Ward vs Multi-Ward
- Multi-Ward configuration section with:
  - Number of wards input (2-100)
  - Area statistics preview
  - Grid layout visualization
  - Real-time calculations
- Proceed button redirects to appropriate routing page

#### `templates/osm_app/multiward_routing.html`
Multi-ward route planning interface:
- Leaflet map showing:
  - Ward boundaries (colored rectangles)
  - Ward labels
  - Centroid markers (depot locations)
  - Computed routes with animated paths
- Right sidebar controls:
  - Global parameters (speed, time window)
  - Collapsible per-ward vehicle assignment
  - Compute button with progress bar
  - Collapsible ward statistics table
  - Download all routes button
- Features:
  - Sequential ward-by-ward computation with progress tracking
  - Auto-suggest vehicles per ward
  - Visual color coding for each ward
  - Marching ants animation on routes
  - Directional arrows on routes

### 5. URL Configuration (`osm_app/urls.py`)

New URL patterns:
```python
path('ward-config/<int:file_id>/', views.ward_config, name='ward_config'),
path('<int:file_id>/create-ward-config/', views.create_ward_config, name='create_ward_config'),
path('<int:file_id>/multiward-routing/', views.multiward_routing, name='multiward_routing'),
path('<int:file_id>/compute-ward-route/', views.compute_ward_route, name='compute_ward_route'),
```

### 6. Navigation Flow Update

Updated `templates/osm_app/crop.html`:
- "Next: Route Planning →" button now redirects to `ward_config` instead of direct `route_planning`
- This ensures all users go through the routing approach selection page

## User Workflow

1. **Upload & Process OSM file** → Extract roads
2. **Crop area** (optional) → Define region of interest
3. **NEW: Select Routing Approach** → Choose Single Ward or Multi-Ward
   - For Single Ward: Proceeds to existing route planning page
   - For Multi-Ward: Configure number of wards
4. **Multi-Ward Configuration** → Select number of wards, view statistics
5. **Ward Creation** → System divides area into grid, calculates statistics
6. **Multi-Ward Route Planning** → 
   - View ward boundaries on map
   - Set vehicles per ward
   - Compute routes sequentially with progress bar
   - Download all routes as GeoJSON

## Key Features

### Performance Optimization
- Large areas divided into smaller wards (default grid layout)
- Each ward processed independently
- Progress bar shows ward-by-ward completion
- Recommended 4-9 wards for optimal performance

### Visual Feedback
- Area < 5 km²: Single Ward recommended (auto-selected)
- Area > 5 km²: Multi-Ward recommended
- Real-time calculations of:
  - Area per ward
  - Ward dimensions (width × height in km)
  - Grid layout (rows × columns)

### Map Visualization
- Colored ward boundaries with dashed borders
- Ward labels positioned at center
- Centroid markers for each ward (depot locations)
- Routes displayed with:
  - Colored lines (per-ward colors)
  - Animated dashed overlay (marching ants)
  - Directional arrows
  - Vehicle popups

### Statistics Tracking
- Per-ward statistics: vehicles, roads, length, status
- Collapsible table for space efficiency
- Status badges: Pending → Computing → Complete/Error

## Technical Details

### Grid Algorithm
- Calculates optimal rows × cols to approximate square grid
- Formula: `cols = ceil(sqrt(num_wards))`, `rows = ceil(num_wards / cols)`
- Even distribution of area across wards

### OSM Data Extraction
- Filters nodes within ward boundaries
- Includes ways with at least one node in ward
- Preserves referenced nodes outside boundaries (for way continuity)
- Creates valid OSM XML for each ward

### Route Computation
- Each ward gets temporary OSM file
- Uses existing Chinese Postman algorithm
- Results stored in Ward model (routes_geojson field)
- Computation time tracked per ward

### Download Feature
- Combines all ward routes into single GeoJSON
- FeatureCollection with all routes
- Filename: `multiward_routes_{config_id}.geojson`

## Database Migrations

Applied migration: `0004_remove_ward_col_remove_ward_geojson_file_and_more`
- Removed old ward fields (col, row, geojson_file, routes_data, total_distance_m)
- Added new ward fields (area_km2, routes_geojson, total_length_m, total_nodes, total_roads)
- Updated WardConfiguration fields
- Created indexes for performance

## Configuration

### Recommended Settings
- **Small areas (< 5 km²)**: Single Ward
- **Medium areas (5-20 km²)**: 4-6 wards
- **Large areas (> 20 km²)**: 6-12 wards
- **Very large areas (> 50 km²)**: 9-16 wards

### Constraints
- Minimum wards: 2
- Maximum wards: 100
- Minimum vehicles per ward: 1
- Maximum vehicles per ward: 20

## Future Enhancements

Potential improvements:
1. **Parallel Processing**: Compute multiple wards simultaneously (backend)
2. **Custom Ward Boundaries**: Manual ward drawing on map
3. **Load Balancing**: Adjust ward sizes based on road density
4. **Ward Optimization**: Minimize boundary crossings
5. **Export Options**: PDF reports, ward-wise CSV files
6. **Historical Analysis**: Compare configurations, track performance

## Testing Checklist

- [ ] Small area (< 5 km²) automatically suggests Single Ward
- [ ] Large area (> 5 km²) can create Multi-Ward configuration
- [ ] Ward grid displays correctly on map
- [ ] Per-ward vehicle assignment works
- [ ] Auto-suggest vehicles calculates correctly
- [ ] Progress bar updates during computation
- [ ] Routes display with correct colors per ward
- [ ] Statistics table shows accurate data
- [ ] Download combines all ward routes
- [ ] Error handling for computation failures

## Notes

- Single Ward route planning page (`route_planning.html`) remains unchanged
- Backward compatible: existing single-ward workflows still work
- Ward configuration stored in database for future reference
- All ward computations logged with timestamps
