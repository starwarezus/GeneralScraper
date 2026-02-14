@echo off
REM Clothing Image Scraper - GUI Mode
REM This script launches the graphical user interface

echo ========================================
echo Clothing Image Scraper - GUI Mode
echo ========================================
echo.

REM Change to the script directory
cd /d "E:\Downloads\General Scraper"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Launching GUI...
echo.

REM Run the GUI scraper
python gui_scraper.py

REM If GUI crashes, show error
if errorlevel 1 (
    echo.
    echo ERROR: GUI failed to start
    echo Make sure all dependencies are installed:
    echo   pip install -r requirements.txt
    pause
)
