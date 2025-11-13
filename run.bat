@echo off
echo Starting OSM Road Processor...
echo.

if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found!
    echo Please run setup.bat first
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python manage.py runserver

pause
