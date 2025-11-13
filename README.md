# OSM Road Processor

A Django web application for processing OpenStreetMap (.osm) files. Extract only roads, crop to specific areas, and export the processed data.

## Features

1. **Upload OSM Files**: Upload .osm XML files from OpenStreetMap
2. **Extract Roads**: Automatically filter OSM data to keep only roads and highways
3. **Interactive Cropping**: Use an interactive map to visually select and crop areas
4. **Export**: Download the processed OSM file

## Installation

### Prerequisites

- Python 3.8 or higher
- pip

### Setup Steps

1. **Create a virtual environment** (recommended):
```cmd
python -m venv venv
venv\Scripts\activate
```

2. **Install dependencies**:
```cmd
pip install -r requirements.txt
```

3. **Run migrations**:
```cmd
python manage.py makemigrations
python manage.py migrate
```

4. **Create a superuser** (optional, for admin access):
```cmd
python manage.py createsuperuser
```

5. **Run the development server**:
```cmd
python manage.py runserver
```

6. **Access the application**:
Open your browser and navigate to: `http://localhost:8000`

## Usage

### Step 1: Upload an OSM File

1. Go to the home page
2. Click "Choose File" and select your .osm file
3. Click "Upload File"

You can download OSM files from:
- [OpenStreetMap Export](https://www.openstreetmap.org/export)
- [BBBike Extract Service](https://extract.bbbike.org/)
- [Geofabrik Downloads](https://download.geofabrik.de/)

### Step 2: Process the File

1. Click the "Process" button next to your uploaded file
2. The system will extract only roads and highways from the OSM data
3. All other features (buildings, amenities, landuse, etc.) will be removed

### Step 3: Crop the Map (Optional)

1. Click the "Crop" button to open the interactive map
2. Click "Draw Selection Rectangle"
3. Click and drag on the map to select your desired area
4. Click "Apply Crop" to trim the OSM file to the selected area
5. You can repeat this process multiple times to refine your selection

### Step 4: Download

Click the "Download" button to download your processed .osm file

## Project Structure

```
infra-UI/
├── manage.py                 # Django management script
├── requirements.txt          # Python dependencies
├── osm_processor/           # Django project settings
│   ├── __init__.py
│   ├── settings.py          # Project settings
│   ├── urls.py              # Main URL configuration
│   ├── wsgi.py              # WSGI configuration
│   └── asgi.py              # ASGI configuration
├── osm_app/                 # Main application
│   ├── __init__.py
│   ├── models.py            # Database models
│   ├── views.py             # View functions
│   ├── urls.py              # App URL configuration
│   ├── admin.py             # Admin configuration
│   ├── apps.py              # App configuration
│   ├── osm_utils.py         # OSM processing utilities
│   └── migrations/          # Database migrations
├── templates/               # HTML templates
│   ├── base.html            # Base template
│   └── osm_app/
│       ├── index.html       # Home page
│       ├── process.html     # Processing page
│       └── crop.html        # Cropping interface
└── media/                   # Uploaded and processed files
    └── osm_files/
        ├── original/        # Original uploaded files
        └── processed/       # Processed files
```

## Technical Details

### OSM Processing

The application uses Python's `xml.etree.ElementTree` to parse and manipulate OSM XML files:

- **Road Extraction**: Filters `<way>` elements with `highway` tags
- **Node Management**: Keeps only nodes referenced by roads
- **Relation Removal**: Removes relations to simplify the output

### Supported Road Types

The following highway types are extracted:
- motorway, trunk, primary, secondary, tertiary
- residential, service, unclassified
- motorway_link, trunk_link, primary_link, secondary_link, tertiary_link
- living_street, pedestrian, track, road

### Frontend Technologies

- **Bootstrap 5**: UI framework
- **Leaflet.js**: Interactive maps
- **OpenStreetMap Tiles**: Base map layer

## Configuration

### File Upload Limits

Edit `osm_processor/settings.py` to change upload limits:

```python
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50 MB
```

### Database

By default, the application uses SQLite. To use a different database, modify the `DATABASES` setting in `settings.py`.

## Troubleshooting

### Import Error: osmium

If you encounter issues installing `osmium`, it's only listed as a dependency but the core functionality uses XML parsing instead. You can remove it from requirements.txt if needed:

```cmd
pip install Django>=4.2,<5.0 lxml>=4.9.0 Pillow>=10.0.0
```

### File Upload Issues

- Ensure the `media/` directory exists and has write permissions
- Check the file size limits in settings.py
- Verify the file is a valid .osm XML file

### Map Not Loading

- Check browser console for JavaScript errors
- Ensure you have an internet connection (for map tiles)
- Verify the OSM file was processed successfully

## Development

### Running Tests

```cmd
python manage.py test
```

### Accessing Admin Panel

1. Create a superuser: `python manage.py createsuperuser`
2. Navigate to `http://localhost:8000/admin`
3. Login with your superuser credentials

## License

This project is provided as-is for educational and development purposes.

## Contributing

Feel free to submit issues and enhancement requests!
