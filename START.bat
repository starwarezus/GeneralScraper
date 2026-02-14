@echo off
REM Master Launcher for Clothing Image Scraper
REM Choose which mode to run

:MENU
cls
echo ========================================
echo   Clothing Image Scraper
echo ========================================
echo.
echo Choose an option:
echo.
echo   1. Run CSV Scraper (uses items.csv)
echo   2. Run JSON Scraper (uses items.json)
echo   3. Run GUI Scraper (graphical interface)
echo   4. First-Time Setup (install dependencies)
echo   5. Create Sample CSV File
echo   6. Create Sample JSON File
echo   7. Open Output Folder
echo   8. View Log File
echo   9. Exit
echo.
set /p choice="Enter your choice (1-9): "

if "%choice%"=="1" goto CSV
if "%choice%"=="2" goto JSON
if "%choice%"=="3" goto GUI
if "%choice%"=="4" goto SETUP
if "%choice%"=="5" goto SAMPLE_CSV
if "%choice%"=="6" goto SAMPLE_JSON
if "%choice%"=="7" goto OPEN_FOLDER
if "%choice%"=="8" goto VIEW_LOG
if "%choice%"=="9" goto EXIT

echo Invalid choice. Please try again.
timeout /t 2 >nul
goto MENU

:CSV
cls
call run_csv_scraper.bat
goto MENU

:JSON
cls
call run_json_scraper.bat
goto MENU

:GUI
cls
call run_gui_scraper.bat
goto MENU

:SETUP
cls
call SETUP.bat
goto MENU

:SAMPLE_CSV
cls
cd /d "E:\Downloads\General Scraper"
echo Creating sample CSV file...
python csv_scraper.py --create-sample items.csv
echo.
echo Sample CSV file created: items.csv
echo You can now edit it in Excel or any text editor.
echo.
pause
goto MENU

:SAMPLE_JSON
cls
cd /d "E:\Downloads\General Scraper"
echo Creating sample JSON file...
python json_scraper.py --create-sample items.json
echo.
echo Sample JSON file created: items.json
echo You can now edit it in any text editor.
echo.
pause
goto MENU

:OPEN_FOLDER
cls
cd /d "E:\Downloads\General Scraper"
if not exist "pics\" (
    echo Creating output folder...
    mkdir "pics"
)
echo Opening output folder...
explorer "E:\Downloads\General Scraper\pics"
goto MENU

:VIEW_LOG
cls
cd /d "E:\Downloads\General Scraper"
if exist "scraper.log" (
    type scraper.log
    echo.
    echo Press any key to return to menu...
    pause >nul
) else (
    echo No log file found yet.
    echo Run the scraper first to generate a log file.
    echo.
    pause
)
goto MENU

:EXIT
cls
echo.
echo Thanks for using Clothing Image Scraper!
echo.
timeout /t 2 >nul
exit
