@echo off
echo ========================================
echo OSM Road Processor - Setup Script
echo ========================================
echo.

echo [1/5] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo Error: Failed to create virtual environment
    pause
    exit /b 1
)
echo Virtual environment created successfully!
echo.

echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat
echo.

echo [3/5] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully!
echo.

echo [4/5] Running database migrations...
python manage.py makemigrations
python manage.py migrate
if errorlevel 1 (
    echo Error: Failed to run migrations
    pause
    exit /b 1
)
echo Database setup complete!
echo.

echo [5/5] Creating media directories...
if not exist "media\osm_files\original" mkdir media\osm_files\original
if not exist "media\osm_files\processed" mkdir media\osm_files\processed
echo Media directories created!
echo.

echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo To start the server, run:
echo   venv\Scripts\activate
echo   python manage.py runserver
echo.
echo Then open http://localhost:8000 in your browser
echo.
pause
