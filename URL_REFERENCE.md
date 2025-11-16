# URL Reference Guide

## Correct URL Patterns

Based on the Django URL configuration where `osm_app.urls` is included at the root level (`path('', include('osm_app.urls'))`), all URLs should NOT have an `/osm/` prefix.

### Main Application URLs

| Page | URL Pattern | Example |
|------|-------------|---------|
| Home/Index | `/` | `http://127.0.0.1:8000/` |
| Upload File | `/upload/` | `http://127.0.0.1:8000/upload/` |
| Process File | `/process/<file_id>/` | `http://127.0.0.1:8000/process/8/` |
| Crop File | `/crop/<file_id>/` | `http://127.0.0.1:8000/crop/8/` |
| Download File | `/download/<file_id>/` | `http://127.0.0.1:8000/download/8/` |
| Get OSM Data | `/get-osm-data/<file_id>/` | `http://127.0.0.1:8000/get-osm-data/8/` |

### Routing URLs

#### Single Ward (Normal)
| Action | URL Pattern | Example |
|--------|-------------|---------|
| Route Planning Page | `/route-planning/<file_id>/` | `http://127.0.0.1:8000/route-planning/8/` |
| Compute Routes (AJAX) | `/compute-routes/<file_id>/` | `http://127.0.0.1:8000/compute-routes/8/` |
| Log Computation (AJAX) | `/log-computation/` | `http://127.0.0.1:8000/log-computation/` |

#### Multi-Ward
| Action | URL Pattern | Example |
|--------|-------------|---------|
| Ward Config Page | `/ward-config/<file_id>/` | `http://127.0.0.1:8000/ward-config/8/` |
| Create Ward Config (AJAX) | `/<file_id>/create-ward-config/` | `http://127.0.0.1:8000/8/create-ward-config/` |
| Multi-Ward Routing Page | `/<file_id>/multiward-routing/` | `http://127.0.0.1:8000/8/multiward-routing/?config_id=1` |
| Compute Ward Route (AJAX) | `/<file_id>/compute-ward-route/` | `http://127.0.0.1:8000/8/compute-ward-route/` |

## Navigation Flow

```
1. Home (/) 
   → Upload file
   
2. Process (/process/8/)
   → Extract roads
   
3. Crop (/crop/8/)
   → [Optional] Define area
   → Click "Next: Route Planning →"
   
4. Ward Config (/ward-config/8/)
   ├─ Select "Single Ward" 
   │  → Goes to /route-planning/8/
   │
   └─ Select "Multi-Ward"
      → Enter number of wards
      → AJAX POST to /8/create-ward-config/
      → Redirects to /8/multiward-routing/?config_id=X
```

## Fixed Issues

### Issue 1: Single Ward URL ❌ → ✅
- **Incorrect**: `/osm/8/route-planning/`
- **Correct**: `/route-planning/8/`
- **Fixed in**: `ward_config.html` line 332

### Issue 2: Create Ward Config URL ❌ → ✅
- **Incorrect**: `/osm/8/create-ward-config/`
- **Correct**: `/8/create-ward-config/`
- **Fixed in**: `ward_config.html` line 344

### Issue 3: Multi-Ward Routing URL ❌ → ✅
- **Incorrect**: `/osm/8/multiward-routing/`
- **Correct**: `/8/multiward-routing/`
- **Fixed in**: `ward_config.html` line 359

### Issue 4: Compute Ward Route URL ❌ → ✅
- **Incorrect**: `/osm/8/compute-ward-route/`
- **Correct**: `/8/compute-ward-route/`
- **Fixed in**: `multiward_routing.html` line 477

## Testing URLs

To verify URLs are working correctly:

1. **Test Ward Config Page**:
   - Navigate to: `http://127.0.0.1:8000/ward-config/8/`
   - Should show Single Ward vs Multi-Ward selection

2. **Test Create Ward Config (via browser console)**:
   ```javascript
   fetch('/8/create-ward-config/', {
       method: 'POST',
       headers: {
           'Content-Type': 'application/json',
           'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
       },
       body: JSON.stringify({
           num_wards: 4,
           ward_layout: 'auto_grid'
       })
   }).then(r => r.json()).then(console.log)
   ```

3. **Test Single Ward Route Planning**:
   - Navigate to: `http://127.0.0.1:8000/route-planning/8/`
   - Should show existing route planning interface

4. **Test Multi-Ward Routing**:
   - After creating ward config, navigate to: `http://127.0.0.1:8000/8/multiward-routing/?config_id=1`
   - Should show ward boundaries on map

## URL Configuration Source

All URL patterns are defined in:
- **File**: `osm_app/urls.py`
- **App Name**: `osm_app`
- **Included At**: Root level in `osm_processor/urls.py`

```python
# osm_processor/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('osm_app.urls')),  # ← No prefix!
]
```

This means all osm_app URLs are at the root level, not under `/osm/`.
