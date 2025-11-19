# Debugging Improvements for Multi-Ward Routing

## Issues Fixed

### 1. Character Encoding Error ✅
**Problem**: `'charmap' codec can't encode characters in position 305863-305866`

**Root Cause**: When creating temporary OSM files for ward computation, the code was using the default system encoding (Windows `cp1252`), which cannot handle special Unicode characters present in OSM data (e.g., street names with diacritics, special symbols).

**Solution**: 
```python
# BEFORE (caused encoding errors on Windows):
with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as tmp_file:

# AFTER (explicitly use UTF-8 encoding):
with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False, encoding='utf-8') as tmp_file:
```

**File**: `osm_app/views.py`, line ~418

---

### 2. Empty Ward Handling ✅
**Problem**: Some wards may have no roads, causing computation to fail silently or produce errors.

**Solution**: Added validation to check if ward contains any ways before attempting route computation:
```python
if '<way' not in ward_osm_xml:
    error_msg = f"Ward {ward.ward_number} has no roads in the selected area"
    return JsonResponse({'success': False, 'error': error_msg})
```

**File**: `osm_app/views.py`, line ~422

---

## Comprehensive Logging Added

### View Layer (`osm_app/views.py`)

Added detailed console logging in `compute_ward_route()`:

```
================================================================================
🔄 Starting computation for Ward 2
   File: example.osm
   Vehicles: 2
   Bounds: (40.123456, -74.123456) to (40.234567, -74.012345)
================================================================================

📊 Extracting OSM data for Ward 2...
✓ Extracted OSM XML: 123456 characters
💾 Creating temporary OSM file...
✓ Temporary file created: C:\Temp\tmp_abc123.osm
🚗 Initializing route partitioner...
🗺️  Computing routes for 2 vehicle(s)...
✓ Routes computed successfully!
   Computation time: 3.45 seconds
   Routes generated: 2 routes
✓ Ward 2 data saved to database
🗑️  Temporary file cleaned up
================================================================================
```

### Ward Extraction Layer (`osm_app/ward_utils.py`)

Added detailed logging in `extract_ward_osm_data()`:

```
  📂 Parsing OSM file: /path/to/file.osm
  ✓ OSM file parsed successfully
  🔍 Pass 1: Collecting nodes within ward boundaries...
  ✓ Found 1234 nodes in ward (out of 5678 total)
  🔍 Pass 2: Collecting ways with nodes in ward...
  ✓ Found 234 ways in ward (out of 890 total)
  ✓ Total referenced nodes: 1456
  📝 Building OSM XML for ward...
  ✓ OSM XML built: 1456 nodes, 234 ways
  🔄 Converting to XML string...
  ✓ XML string created: 123456 characters
```

### Routing Algorithm Layer (`osm_app/routing_utils.py`)

Enhanced logging in `compute_routes()`:

```
============================================================
🚗 ROUTE COMPUTATION STARTED
   Vehicles requested: 2
============================================================
📖 Step 1: Parsing OSM data...
   ✓ Nodes: 1456, Ways: 234
🔨 Step 2: Building graph...
   ✓ Graph nodes: 1456, edges: 468
📍 Step 3: Finding centroid depot...
   ✓ Depot at: (40.123456, -74.123456)
🔗 Step 4: Extracting connected component...
   ✓ Component nodes: 1450, edges: 465
⚡ Step 5: Making graph Eulerian...
   ✓ Eulerian graph edges: 520
   ✓ Added 55 edge pairs to balance odd-degree nodes
🔄 Step 6: Extracting Eulerian circuit...
   ✓ Circuit contains 520 edges
✂️  Step 7: Splitting circuit into 2 segments...
   ✓ Segments created: 2
      Vehicle 1: 260 edges
      Vehicle 2: 260 edges
🗺️  Step 8: Building vehicle routes...
   Building route for Vehicle 1...
   ✓ Vehicle 1: 261 nodes, 5234.56 m
   Building route for Vehicle 2...
   ✓ Vehicle 2: 261 nodes, 5123.45 m

✅ ROUTE COMPUTATION COMPLETED
   Total routes: 2
============================================================
```

### Error Logging

Enhanced error messages with full context:

```
================================================================================
❌ ERROR in Ward 2
   Error type: UnicodeEncodeError
   Error message: 'charmap' codec can't encode character '\u0142'...
================================================================================
[Full traceback here]
================================================================================
```

---

## How to Use the Logs

### 1. Monitor Terminal Output
When running the development server, watch the terminal for:
- **Progress indicators** (emoji symbols show current step)
- **Success messages** (✓ marks)
- **Warnings** (⚠️ symbols)
- **Error details** (❌ marks with full tracebacks)

### 2. Identify Bottlenecks
Look for steps that take longer than expected:
- Parsing OSM data (should be < 1 second)
- Building graph (depends on size, typically < 2 seconds)
- Making Eulerian (can be slow for large graphs)
- Extracting circuit (usually fast)

### 3. Debug Ward-Specific Issues
Each ward computation is clearly separated with banners:
```
================================================================================
🔄 Starting computation for Ward 3
...
================================================================================
```

This makes it easy to identify which ward failed and at what step.

### 4. Verify Data Integrity
Check the statistics logged:
- **Nodes found**: Should be > 0
- **Ways found**: Should be > 0
- **Connected component**: Should be close to total nodes (isolated nodes are filtered)
- **Routes generated**: Should match requested vehicles

---

## Common Issues and Solutions

### Issue: Ward Has No Roads
**Log Message**: `⚠️  WARNING: Ward 2 has no roads in the selected area`

**Solution**: 
- Reduce number of wards
- The area division may have created a ward with no roads
- Some wards may fall in areas without road coverage (parks, water bodies)

### Issue: Character Encoding Error
**Log Message**: `❌ ERROR in Ward 2... UnicodeEncodeError`

**Solution**: ✅ **FIXED** - Now using UTF-8 encoding for all file operations

### Issue: Disconnected Graph
**Log Message**: `✓ Component nodes: 50` (much less than total nodes)

**Solution**: 
- The ward area may have disconnected road segments
- Routes will only cover the largest connected component
- Consider adjusting ward boundaries

### Issue: Very Long Computation Time
**Log Message**: Step 5 (Making Eulerian) takes > 30 seconds

**Solution**:
- Ward may be too large
- Increase number of wards to reduce per-ward size
- Target: 200-500 edges per ward for optimal performance

---

## Testing Recommendations

1. **Test with various ward counts**: Try 2, 4, 6, 9 wards
2. **Monitor terminal output**: Watch for any warnings or errors
3. **Check timing**: Note computation time for each ward
4. **Verify route quality**: Ensure all wards generate valid routes
5. **Test edge cases**: Very small wards, wards at boundaries

---

## Performance Metrics to Watch

From the logs, track:
- ✅ **Extraction time**: Should be < 1 second per ward
- ✅ **Computation time**: Target < 10 seconds per ward
- ✅ **Success rate**: All wards should complete successfully
- ✅ **Route count**: Should match requested vehicles

Expected output for 4 wards:
```
Ward 1: ✓ Complete (3.2s)
Ward 2: ✓ Complete (2.8s)
Ward 3: ✓ Complete (3.5s)
Ward 4: ✓ Complete (3.1s)
Total: 12.6 seconds
```

This is significantly faster than processing the entire area at once (which might take 45+ seconds).
