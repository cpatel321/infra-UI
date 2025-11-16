# Multi-Ward Refactoring - Modular API Architecture

## Overview

Refactored the multi-ward routing system to use a clean, modular architecture where:
1. **Single ward routing is a standalone function** that can be called from anywhere
2. **Multi-ward routing calls the single ward API** for each ward independently
3. **No more complex OSM extraction** - bounds-based filtering happens in one place
4. **Cleaner error handling** - each ward computation is isolated

---

## New Architecture

### Core Function: `compute_single_ward_routes()`

**Location**: `osm_app/views.py`

This is the **modular core** that handles all routing computation:

```python
compute_single_ward_routes(
    osm_file_path,    # Path to OSM file
    num_vehicles,     # Number of vehicles
    bounds=None,      # Optional: crop to bounds
    ward_label="Area" # Label for logging
)

Returns:
{
    'success': True/False,
    'routes': GeoJSON FeatureCollection,
    'computation_time': float (seconds),
    'stats': dict (nodes, roads, length),
    'error': str (if failed)
}
```

### How It Works

#### 1. **If bounds provided** (multi-ward case):
```
Original OSM File
    ↓
Parse XML
    ↓
Filter nodes within bounds
    ↓
Filter ways with nodes in bounds
    ↓
Create temporary cropped OSM file (UTF-8)
    ↓
Run routing algorithm
    ↓
Delete temporary file
    ↓
Return routes
```

#### 2. **If no bounds** (single ward/normal case):
```
Original OSM File
    ↓
Run routing algorithm directly
    ↓
Return routes
```

---

## API Endpoints

### 1. Single Ward / Normal Route Planning

**Endpoint**: `POST /compute-routes/<file_id>/`

**Used by**: `route_planning.html` (existing single-ward page)

**Process**:
```javascript
fetch('/compute-routes/8/', {
    method: 'POST',
    body: JSON.stringify({ k: 3 })  // 3 vehicles
})
```

**Backend**:
```python
def compute_routes(request, file_id):
    # Calls compute_single_ward_routes() with no bounds
    result = compute_single_ward_routes(
        osm_file_path=osm_record.processed_file.path,
        num_vehicles=k,
        bounds=None,  # Use entire file
        ward_label="Full Area"
    )
```

### 2. Multi-Ward Route Planning

**Endpoint**: `POST /<file_id>/compute-ward-route/`

**Used by**: `multiward_routing.html`

**Process**:
```javascript
fetch('/8/compute-ward-route/', {
    method: 'POST',
    body: JSON.stringify({
        ward_id: 123,
        num_vehicles: 2
    })
})
```

**Backend**:
```python
def compute_ward_route(request, file_id):
    # Calls compute_single_ward_routes() with ward bounds
    result = compute_single_ward_routes(
        osm_file_path=osm_record.processed_file.path,
        num_vehicles=num_vehicles,
        bounds={
            'min_lat': ward.min_lat,
            'max_lat': ward.max_lat,
            'min_lon': ward.min_lon,
            'max_lon': ward.max_lon
        },
        ward_label=f"Ward {ward.ward_number}"
    )
```

---

## Key Improvements

### ✅ 1. Eliminated Dependency on `ward_utils.py`

**Before**: Complex `extract_ward_osm_data()` function with separate XML handling

**After**: Bounds-based filtering integrated directly in `compute_single_ward_routes()`

### ✅ 2. UTF-8 Encoding Built-In

All temporary files created with explicit UTF-8 encoding:
```python
with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', 
                                  delete=False, encoding='utf-8') as tmp_file:
```

**Fixes**: Character encoding errors on Windows (charmap codec issues)

### ✅ 3. Unified Error Handling

Both single-ward and multi-ward use the same error handling:
- Returns structured dict with `success` flag
- Includes error messages
- Cleans up temp files automatically
- Full traceback logging

### ✅ 4. Simplified Flow

**Single Ward**:
```
User clicks "Calculate Routes"
    ↓
JavaScript calls compute_routes API
    ↓
compute_single_ward_routes() with no bounds
    ↓
Routes returned
```

**Multi-Ward**:
```
User clicks "Calculate Optimal Paths"
    ↓
JavaScript loops through wards
    ↓
For each ward: call compute_ward_route API
    ↓
compute_single_ward_routes() with ward bounds
    ↓
Routes stitched together in frontend
```

### ✅ 5. Automatic Statistics Updates

Ward statistics are automatically updated after computation:
```python
if result['success']:
    ward.routes_geojson = result['routes']
    ward.computation_time = result['computation_time']
    ward.total_nodes = result['stats'].get('total_nodes', 0)
    ward.total_roads = result['stats'].get('total_roads', 0)
    ward.total_length_m = result['stats'].get('total_length_m', 0)
    ward.save()
```

---

## Benefits of This Architecture

### 🎯 Modularity
- Core routing logic in one place
- Can be reused for future features (e.g., custom area selection, neighborhood routing)
- Easy to test and debug

### 🔒 Isolation
- Each ward computation is independent
- Failure in one ward doesn't affect others
- Temporary files are automatically cleaned up

### 🚀 Performance
- No intermediate XML string manipulations
- Direct file operations with proper encoding
- Minimal memory overhead

### 🛠️ Maintainability
- Single source of truth for routing
- Consistent error handling
- Clear separation of concerns

### 📊 Consistency
- Same logging format for all computations
- Unified statistics structure
- Standard GeoJSON output

---

## What Was Removed

### Deprecated Functions (no longer needed):
- `extract_ward_osm_data()` in `ward_utils.py` - **Replaced** by inline bounds filtering
- Complex XML string manipulation - **Replaced** by direct file operations
- Separate temporary file creation logic - **Unified** in core function

### Note
`ward_utils.py` still contains:
- ✅ `divide_area_into_wards()` - Still used for ward creation
- ✅ `calculate_area_km2()` - Still used for area calculations
- ✅ `calculate_ward_statistics()` - Still used during ward config creation

Only the OSM extraction logic was replaced.

---

## Testing the Refactored System

### Test 1: Single Ward (Normal Mode)
1. Upload and process OSM file
2. Go to route planning (single ward)
3. Enter number of vehicles
4. Click "Calculate Routes"
5. **Expected**: Routes displayed, no errors

### Test 2: Multi-Ward Mode
1. After crop, select "Multi-Ward"
2. Enter number of wards (e.g., 4)
3. Click "Proceed to Route Planning"
4. Set vehicles per ward
5. Click "Calculate Optimal Paths"
6. **Expected**: 
   - Terminal shows progress for each ward
   - Each ward computes independently
   - Routes displayed with different colors
   - No encoding errors

### Test 3: Error Handling
1. Create wards where some may have no roads
2. Attempt computation
3. **Expected**: 
   - Wards with no roads show error
   - Other wards complete successfully
   - Clear error messages in UI

---

## Console Output Example

```
================================================================================
🔄 Computing routes for Ward 1
   Vehicles: 2
   Bounds: (40.123456, -74.123456) to (40.234567, -74.012345)
================================================================================

📊 Extracting area data with bounds...
   ✓ Found 1234 nodes in bounds
   ✓ Found 234 ways in bounds
   ✓ Created temporary bounded file
🚗 Initializing route partitioner...
🗺️  Computing routes for 2 vehicle(s)...

============================================================
🚗 ROUTE COMPUTATION STARTED
   Vehicles requested: 2
============================================================
[... algorithm steps ...]
✅ ROUTE COMPUTATION COMPLETED
   Total routes: 2
============================================================

✓ Routes computed successfully!
   Computation time: 3.45 seconds
   Routes generated: 2 routes
================================================================================
```

---

## Migration Path

### No Changes Required For:
- ✅ Database models (Ward, WardConfiguration)
- ✅ URL patterns
- ✅ Frontend JavaScript
- ✅ Templates (ward_config.html, multiward_routing.html)

### Automatic Benefits:
- ✅ UTF-8 encoding (fixes character errors)
- ✅ Better logging
- ✅ Cleaner error messages
- ✅ Faster execution (less overhead)

The refactoring is **backward compatible** - existing functionality works exactly the same, but with better reliability.
