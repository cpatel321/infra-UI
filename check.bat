@echo off
echo ========================================
echo OSM Road Processor - System Check
echo ========================================
echo.

echo Checking Python installation...
python --version
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://www.python.org/
    pause
    exit /b 1
)
echo [OK] Python found
echo.

echo Checking pip installation...
pip --version
if errorlevel 1 (
    echo [ERROR] pip is not available
    pause
    exit /b 1
)
echo [OK] pip found
echo.

echo Checking virtual environment...
if exist "venv\Scripts\python.exe" (
    echo [OK] Virtual environment exists
) else (
    echo [WARNING] Virtual environment not found
    echo Run setup.bat to create it
)
echo.

echo Checking Django installation...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    python -c "import django; print('[OK] Django version:', django.get_version())" 2>nul
    if errorlevel 1 (
        echo [WARNING] Django not installed in virtual environment
        echo Run setup.bat to install dependencies
    )
) else (
    echo [WARNING] Cannot check - virtual environment not found
)
echo.

echo Checking database...
if exist "db.sqlite3" (
    echo [OK] Database file exists
) else (
    echo [WARNING] Database not initialized
    echo Run setup.bat or: python manage.py migrate
)
echo.

echo Checking media directories...
if exist "media\osm_files\original" (
    echo [OK] Original files directory exists
) else (
    echo [WARNING] media\osm_files\original not found
)

if exist "media\osm_files\processed" (
    echo [OK] Processed files directory exists
) else (
    echo [WARNING] media\osm_files\processed not found
)
echo.

echo Checking project files...
set MISSING=0

if not exist "manage.py" (
    echo [ERROR] manage.py not found
    set MISSING=1
)

if not exist "osm_processor\settings.py" (
    echo [ERROR] settings.py not found
    set MISSING=1
)

if not exist "osm_app\views.py" (
    echo [ERROR] views.py not found
    set MISSING=1
)

if not exist "osm_app\osm_utils.py" (
    echo [ERROR] osm_utils.py not found
    set MISSING=1
)

if not exist "templates\base.html" (
    echo [ERROR] base.html not found
    set MISSING=1
)

if %MISSING%==0 (
    echo [OK] All core files present
) else (
    echo [ERROR] Some project files are missing
)
echo.

echo ========================================
echo System Check Complete
echo ========================================
echo.

if exist "venv\Scripts\activate.bat" (
    if exist "db.sqlite3" (
        echo System appears to be ready!
        echo Run: run.bat to start the server
    ) else (
        echo Please run setup.bat to complete installation
    )
) else (
    echo Please run setup.bat to complete installation
)
echo.

pause
