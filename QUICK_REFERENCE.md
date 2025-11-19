# Quick Reference Guide

## New Features at a Glance

### 1. Depot Management
**Access**: Django Admin → Depots
**Actions**: 
- Add new depot (name, location, capacity)
- Mark depots as active/inactive
- View which wards are assigned to each depot

### 2. Ward Validation
**Automatic**: Runs when creating ward configuration
**Checks**:
- Has roads ✅
- Has population ✅
- Reasonable size ✅
- Connected network ✅
- Depot accessible ✅

### 3. Improved Vehicle Calculation
**Formula**: 
```
Depot Travel = (Distance × 2) / Speed
Available Time = Shift Duration - Depot Travel
Vehicles by Capacity = Waste / Vehicle Capacity
Vehicles by Time = Roads / (Speed × Available Time)
Suggested = max(Capacity, Time), capped at 20
```

### 4. UI Improvements
- Ward boundaries: Black, 4px thick, solid
- Vehicle routes: 20 distinct colors (no more black!)
- Warnings: Yellow badges for issues, red for critical
- Depot info: Shows which depot assigned and distance

---

## Common Tasks

### Add a New Depot
1. Go to Django Admin (`/admin/`)
2. Click "Depots" → "Add Depot"
3. Fill in:
   - Name: "North Transfer Station"
   - Location: Lat/Lon (use Google Maps to find)
   - Capacity: 30000 (in kg/day)
   - Active: ✅
4. Save

### Create Wards with Validation
1. Upload OSM → Process → Crop
2. Click "Configure Wards"
3. Set parameters (wards, waste, capacity)
4. Enable WorldPop if needed
5. Submit → Check console for validation results
6. Review warnings in multi-ward page

### Interpret Validation Warnings
- **"No roads"** → Critical, exclude this ward
- **"Low density"** → Consider merging with neighbor
- **"Far from depot"** → Increase shift time or add closer depot
- **"Very large"** → May need 2 shifts or split into smaller wards

### Use Population-Balanced Division
```python
# In views.py, replace:
config = divide_area_into_wards(osm_file, num_wards)

# With:
from django.conf import settings
config = divide_area_by_population(
    osm_file, 
    num_wards, 
    str(settings.POPULATION_RASTER_PATH)
)
```

---

## Troubleshooting

### Ward shows "Population: 0"
**Fix**: Make sure server running with venv Python:
```bash
C:\Users\chand\Desktop\infra-UI\venv\Scripts\python.exe manage.py runserver
```

### Warning: "No active depots found"
**Fix**: Add depots via admin or run:
```bash
python manage.py shell -c "exec(open('add_sample_depots.py').read())"
```

### Ward validation always fails
**Check**: 
1. Does ward have roads? (total_roads > 0)
2. Is OSM data cropped correctly?
3. Check console output for specific issue

---

## API/JSON Response

When creating wards, the JSON response now includes:
```json
{
  "success": true,
  "config_id": 123,
  "wards": [
    {
      "ward_number": 1,
      "population": 558546,
      "area_km2": 27.73,
      "density": 20138,
      "roads": 156,
      "length_m": 34200,
      "validation_warnings": [],
      "has_valid_data": true,
      "is_connected": true,
      "assigned_depot": "Kanpur Central Depot",
      "depot_distance_km": 5.2
    }
  ]
}
```

---

## Console Output Reference

### Good Ward
```
Ward 1:
  📊 Statistics: 156 roads, 34.2 km total length
  🔍 Validating ward 1...
  ✅ All checks passed
  📍 Population: 558,546 people (20,138/km²)
  🚛 Depot: Kanpur Central (5.2 km)
```

### Ward with Warnings
```
Ward 3:
  📊 Statistics: 12 roads, 3.1 km total length
  🔍 Validating ward 3...
  ⚠️  Very low population density (85/km²)
  ⚠️  Small area (1.2 km²) - consider merging
  📍 Population: 102 people (85/km²)
  🚛 Depot: Kanpur South (45.8 km)
  ⚠️  Far from depot - may impact shift time
```

### Critical Issue
```
Ward 5:
  📊 Statistics: 0 roads, 0.0 km total length
  🔍 Validating ward 5...
  ❌ No roads - cannot compute routes
  📍 Population: 0 people (0/km²)
```

---

## Database Schema

### Depot Table
| Field | Type | Description |
|-------|------|-------------|
| name | CharField | Depot name |
| address | TextField | Full address |
| lat | FloatField | Latitude |
| lon | FloatField | Longitude |
| capacity_kg | FloatField | Daily capacity (kg) |
| active | BooleanField | Is depot operational? |

### Ward Table (New Fields)
| Field | Type | Description |
|-------|------|-------------|
| assigned_depot | ForeignKey | Linked depot |
| depot_distance_km | FloatField | Distance to depot |
| is_connected | BooleanField | Roads form connected network? |
| has_valid_data | BooleanField | Passes validation? |
| validation_warnings | JSONField | List of warning messages |
| last_validated | DateTimeField | When validated |

---

## Next Steps (Optional Enhancements)

1. **Add more depots**: Cover entire city with transfer stations
2. **Traffic patterns**: Add time-of-day speed adjustments
3. **Historical tracking**: Record actual vs planned performance
4. **Mobile app**: Field workers report collection status
5. **Road network division**: Replace grid with graph partitioning
6. **Multi-city support**: Scale beyond Kanpur

---

## Support

- Technical docs: `REAL_WORLD_IMPROVEMENTS.md`
- Simple explanation: `SIMPLE_SUMMARY.md`
- Code: `osm_app/ward_utils.py`, `osm_app/models.py`
- Admin: `/admin/osm_app/`

## Version
- Last updated: November 19, 2025
- Migration: 0006_depot_ward_depot_distance_km_ward_has_valid_data_and_more
