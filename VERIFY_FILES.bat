@echo off
REM File Verification and Download Helper
echo ========================================
echo Required Files Check
echo ========================================
echo.
echo Checking E:\Downloads\General Scraper\
echo.

cd /d "E:\Downloads\General Scraper"

echo Required Python Files:
echo.

if exist "clothing_image_scraper.py" (
    echo [OK] clothing_image_scraper.py
) else (
    echo [MISSING] clothing_image_scraper.py  ^<-- YOU NEED THIS FILE!
)

if exist "csv_scraper.py" (
    echo [OK] csv_scraper.py
) else (
    echo [MISSING] csv_scraper.py
)

if exist "json_scraper.py" (
    echo [OK] json_scraper.py
) else (
    echo [MISSING] json_scraper.py
)

if exist "gui_scraper.py" (
    echo [OK] gui_scraper.py
) else (
    echo [MISSING] gui_scraper.py
)

if exist "batch_example.py" (
    echo [OK] batch_example.py
) else (
    echo [MISSING] batch_example.py
)

if exist "requirements.txt" (
    echo [OK] requirements.txt
) else (
    echo [MISSING] requirements.txt
)

echo.
echo Required Batch Files:
echo.

if exist "START.bat" (
    echo [OK] START.bat
) else (
    echo [MISSING] START.bat
)

if exist "SETUP.bat" (
    echo [OK] SETUP.bat
) else (
    echo [MISSING] SETUP.bat
)

if exist "run_csv_scraper.bat" (
    echo [OK] run_csv_scraper.bat
) else (
    echo [MISSING] run_csv_scraper.bat
)

if exist "run_json_scraper.bat" (
    echo [OK] run_json_scraper.bat
) else (
    echo [MISSING] run_json_scraper.bat
)

if exist "run_gui_scraper.bat" (
    echo [OK] run_gui_scraper.bat
) else (
    echo [MISSING] run_gui_scraper.bat
)

echo.
echo ========================================
echo.
echo IMPORTANT: Make sure you downloaded ALL files from Claude!
echo.
echo You should have downloaded these files:
echo   1. clothing_image_scraper.py  ^<-- MOST IMPORTANT!
echo   2. csv_scraper.py
echo   3. json_scraper.py
echo   4. gui_scraper.py
echo   5. batch_example.py
echo   6. requirements.txt
echo   7. items.csv
echo   8. items.json
echo   9. All .bat files (START.bat, SETUP.bat, etc.)
echo.
echo All files must be placed directly in:
echo   E:\Downloads\General Scraper\
echo.
echo NOT in a subfolder!
echo.
pause
