# Quick Start Guide

## Getting Started in 3 Steps

### Step 1: Setup (First Time Only)

Run the setup script:
```cmd
setup.bat
```

This will:
- Create a Python virtual environment
- Install all required packages
- Setup the database
- Create necessary directories

### Step 2: Start the Server

Run the server script:
```cmd
run.bat
```

Or manually:
```cmd
venv\Scripts\activate
python manage.py runserver
```

### Step 3: Open in Browser

Navigate to: **http://localhost:8000**

---

## Testing the App

A sample OSM file (`sample_map.osm`) is included in the project root. Use it to test the application:

1. Upload `sample_map.osm`
2. Click "Process" to extract roads
3. Click "Crop" to see the interactive map
4. Draw a selection rectangle on the map
5. Click "Apply Crop" to trim the area
6. Click "Download" to get your processed file

---

## Getting Real OSM Data

Download OSM files from these sources:

### OpenStreetMap Export
1. Go to https://www.openstreetmap.org/export
2. Select "Manually select a different area"
3. Draw a box on the map (keep it small, < 50MB)
4. Click "Export"

### BBBike Extract Service
- https://extract.bbbike.org/
- Select city or draw custom area
- Choose OSM XML format

### Geofabrik Downloads
- https://download.geofabrik.de/
- Download regional extracts
- **Note**: Some files may be too large for this tool

---

## Workflow Example

```
1. Upload File
   ↓
2. Process (Extract Roads)
   ↓
3. View on Interactive Map
   ↓
4. Draw Crop Rectangle (Optional)
   ↓
5. Apply Crop (Optional)
   ↓
6. Download Processed File
```

---

## Common Commands

### Create Admin User
```cmd
python manage.py createsuperuser
```
Access admin at: http://localhost:8000/admin

### Reset Database
```cmd
del db.sqlite3
python manage.py migrate
```

### View All Uploaded Files
```cmd
python manage.py shell
>>> from osm_app.models import OSMFile
>>> OSMFile.objects.all()
```

---

## Troubleshooting

**Problem**: Server won't start
- **Solution**: Make sure you activated the virtual environment first
  ```cmd
  venv\Scripts\activate
  ```

**Problem**: Can't upload files
- **Solution**: Check that `media/osm_files/` directories exist

**Problem**: Map not displaying
- **Solution**: Check browser console for errors. Ensure internet connection for map tiles.

**Problem**: File too large
- **Solution**: Edit `osm_processor/settings.py`:
  ```python
  FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100 MB
  ```

---

## Features Summary

✅ Upload .osm files  
✅ Extract only roads/highways  
✅ Interactive map visualization  
✅ Draw selection rectangle to crop  
✅ Download processed files  
✅ Support for multiple file processing  
✅ File history tracking  

---

## Next Steps

- Experiment with different OSM files
- Try cropping to specific neighborhoods
- Use the admin panel to manage files
- Export data for use in GIS software

Enjoy processing your OSM files! 🗺️
