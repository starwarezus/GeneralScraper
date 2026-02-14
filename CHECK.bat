@echo off
REM Diagnostic Tool for Clothing Image Scraper
REM Checks if all required files are present

echo ========================================
echo Clothing Image Scraper - Diagnostics
echo ========================================
echo.

cd /d "E:\Downloads\General Scraper"

echo Checking required files...
echo.

set missing=0

REM Check Python
echo [1/10] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo    [X] MISSING - Python is not installed or not in PATH
    echo        Download from: https://www.python.org/downloads/
    set missing=1
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo    [OK] %%i
)

REM Check main scraper
echo [2/10] Checking clothing_image_scraper.py...
if exist "clothing_image_scraper.py" (
    echo    [OK] Found
) else (
    echo    [X] MISSING - This is the main scraper file!
    set missing=1
)

REM Check CSV scraper
echo [3/10] Checking csv_scraper.py...
if exist "csv_scraper.py" (
    echo    [OK] Found
) else (
    echo    [X] MISSING - CSV batch scraper
    set missing=1
)

REM Check JSON scraper
echo [4/10] Checking json_scraper.py...
if exist "json_scraper.py" (
    echo    [OK] Found
) else (
    echo    [X] MISSING - JSON batch scraper
    set missing=1
)

REM Check GUI scraper
echo [5/10] Checking gui_scraper.py...
if exist "gui_scraper.py" (
    echo    [OK] Found
) else (
    echo    [X] MISSING - GUI scraper
    set missing=1
)

REM Check requirements
echo [6/10] Checking requirements.txt...
if exist "requirements.txt" (
    echo    [OK] Found
) else (
    echo    [X] MISSING - Requirements file
    set missing=1
)

REM Check CSV file
echo [7/10] Checking items.csv...
if exist "items.csv" (
    echo    [OK] Found
) else (
    echo    [!] NOT FOUND - Will be created when you run the scraper
)

REM Check JSON file
echo [8/10] Checking items.json...
if exist "items.json" (
    echo    [OK] Found
) else (
    echo    [!] NOT FOUND - Will be created when you run the scraper
)

REM Check output directory
echo [9/10] Checking output directory...
if exist "pics\" (
    echo    [OK] Found: pics\
) else (
    echo    [!] NOT FOUND - Will be created when you run the scraper
)

REM Check Python packages
echo [10/10] Checking Python packages...
python -c "import requests; import bs4" >nul 2>&1
if errorlevel 1 (
    echo    [X] MISSING - Required packages not installed
    echo        Run SETUP.bat to install packages
    set missing=1
) else (
    echo    [OK] All required packages installed
)

echo.
echo ========================================

if %missing%==1 (
    echo STATUS: ISSUES FOUND
    echo ========================================
    echo.
    echo Please fix the missing items above.
    echo.
    echo Common fixes:
    echo   - If Python is missing: Install Python from https://www.python.org/downloads/
    echo   - If packages are missing: Run SETUP.bat
    echo   - If .py files are missing: Re-download all files to this folder
    echo.
) else (
    echo STATUS: ALL SYSTEMS GO!
    echo ========================================
    echo.
    echo Everything looks good!
    echo You can now run the scraper using:
    echo   - START.bat (recommended)
    echo   - run_csv_scraper.bat
    echo   - run_json_scraper.bat
    echo   - run_gui_scraper.bat
    echo.
)

pause
