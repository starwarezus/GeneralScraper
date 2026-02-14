@echo off
REM First-Time Setup for Clothing Image Scraper
REM This script installs required Python packages

echo ========================================
echo Clothing Image Scraper - Setup
echo ========================================
echo.
echo This script will install the required Python packages.
echo Make sure you have Python installed first!
echo.
pause

REM Change to the script directory
cd /d "E:\Downloads\General Scraper"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo Python found! Installing required packages...
echo.

REM Install required packages
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install packages
    echo Try running this as Administrator
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo You can now use the scraper:
echo   - run_csv_scraper.bat   (for CSV files)
echo   - run_json_scraper.bat  (for JSON files)
echo   - run_gui_scraper.bat   (for GUI interface)
echo.
pause
