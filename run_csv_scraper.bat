@echo off
REM Clothing Image Scraper - CSV Batch File
REM This script runs the CSV scraper with your items.csv file

echo ========================================
echo Clothing Image Scraper - CSV Mode
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

REM Check if items.csv exists
if not exist "items.csv" (
    echo ERROR: items.csv not found!
    echo.
    echo Creating a sample items.csv file...
    python csv_scraper.py --create-sample items.csv
    echo.
    echo Sample file created: items.csv
    echo Please edit items.csv with your items and run this batch file again.
    pause
    exit /b 1
)

REM Create output directory if it doesn't exist
if not exist "E:\Downloads\General Scraper\pics\" (
    echo Creating output directory: E:\Downloads\General Scraper\pics\
    mkdir "E:\Downloads\General Scraper\pics\"
)

echo Starting scraper...
echo Input file: items.csv
echo Output directory: E:\Downloads\General Scraper\pics\
echo.

REM Run the scraper with log file
python csv_scraper.py items.csv --output "E:\Downloads\General Scraper\pics" --log scraper.log

echo.
echo ========================================
echo Scraping Complete!
echo ========================================
echo Images saved to: E:\Downloads\General Scraper\pics\
echo Log file saved to: scraper.log
echo.
pause
