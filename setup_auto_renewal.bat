@echo off
REM Setup script for Windows Task Scheduler auto-renewal
REM This creates an automated daily check for session renewal

setlocal enabledelayedexpansion

echo.
echo ================================================================================
echo REELFORGE SESSION AUTO-RENEWAL SETUP
echo ================================================================================
echo.
echo This script will set up Windows Task Scheduler to automatically check and
echo renew your Instagram session every day at 2:00 AM.
echo.

REM Get current directory (project root)
set PROJECT_DIR=%~dp0
set PYTHON_SCRIPT=%PROJECT_DIR%auto_renew_session.py

echo Detected project directory: %PROJECT_DIR%
echo Script location: %PYTHON_SCRIPT%
echo.

REM Get Python executable path
for /f "tokens=*" %%i in ('where python') do set PYTHON_EXE=%%i

if "%PYTHON_EXE%"=="" (
    echo ERROR: Python not found in PATH
    echo Please install Python and add it to your PATH environment variable
    pause
    exit /b 1
)

echo Found Python: %PYTHON_EXE%
echo.

echo ================================================================================
echo SETUP OPTIONS
echo ================================================================================
echo.
echo This will create an automated daily renewal check.
echo.
echo OPTION 1: Auto-Renewal (Recommended)
echo   - Requires: INSTA_USERNAME and INSTA_PASSWORD environment variables
echo   - Will attempt password login monthly
echo   - Sends alert if manual renewal needed
echo.
echo OPTION 2: Daily Check Only
echo   - Checks if renewal is needed
echo   - Sends alert when action is required
echo   - You perform renewal manually when prompted
echo.

choice /C 12 /N /M "Select option (1 or 2): "
set CHOICE=%errorlevel%

if %CHOICE%==1 (
    echo.
    echo Setting up AUTO-RENEWAL...
    echo.
    echo You'll need to set environment variables for auto-renewal to work:
    echo   INSTA_USERNAME = your Instagram username
    echo   INSTA_PASSWORD = your Instagram password
    echo.
    set /p USERNAME="Enter Instagram username (or press Enter to skip): "
    set /p PASSWORD="Enter Instagram password (or press Enter to skip): "
    
    if not "!USERNAME!"=="" (
        setx INSTA_USERNAME "!USERNAME!"
        echo ✅ Set INSTA_USERNAME environment variable
    )
    
    if not "!PASSWORD!"=="" (
        setx INSTA_PASSWORD "!PASSWORD!"
        echo ✅ Set INSTA_PASSWORD environment variable
    )
    
    if "!USERNAME!"=="" (
        echo ⚠️  Skipped environment variable setup
        echo    You can set them manually later for auto-renewal
    )
)

echo.
echo ================================================================================
echo CREATING SCHEDULED TASK
echo ================================================================================
echo.

REM Create the scheduled task
schtasks /create ^
    /tn "ReelForge\Session Auto-Renewal" ^
    /tr "\"!PYTHON_EXE!\" \"!PYTHON_SCRIPT!\"" ^
    /sc daily ^
    /st 02:00 ^
    /ru SYSTEM ^
    /rl HIGHEST ^
    /f

if %errorlevel%==0 (
    echo ✅ Task created successfully!
    echo.
    echo SCHEDULED TASK DETAILS:
    echo   Name: ReelForge\Session Auto-Renewal
    echo   Schedule: Daily at 2:00 AM
    echo   Action: Python script for session renewal check
    echo.
) else if %errorlevel%==1 (
    echo.
    echo ⚠️  Task may already exist. Attempting to update...
    echo.
    
    schtasks /delete "ReelForge\Session Auto-Renewal" /f
    
    schtasks /create ^
        /tn "ReelForge\Session Auto-Renewal" ^
        /tr "\"!PYTHON_EXE!\" \"!PYTHON_SCRIPT!\"" ^
        /sc daily ^
        /st 02:00 ^
        /ru SYSTEM ^
        /rl HIGHEST ^
        /f
    
    if %errorlevel%==0 (
        echo ✅ Task updated successfully!
    ) else (
        echo ❌ Failed to create/update task
        echo.
        echo MANUAL SETUP REQUIRED:
        echo 1. Open Windows Task Scheduler (taskschd.msc)
        echo 2. Create Basic Task with:
        echo    - Name: ReelForge Session Auto-Renewal
        echo    - Trigger: Daily at 2:00 AM
        echo    - Action: Start a program
        echo    - Program: !PYTHON_EXE!
        echo    - Arguments: !PYTHON_SCRIPT!
        echo 3. Set to run with highest privileges
        pause
        exit /b 1
    )
) else (
    echo ❌ Error creating task (code: %errorlevel%)
    pause
    exit /b %errorlevel%
)

echo.
echo ================================================================================
echo SETUP COMPLETE ✅
echo ================================================================================
echo.
echo Your system will now:
echo   • Check session validity every day at 2:00 AM
echo   • Attempt auto-renewal if session is 28+ days old
if not "!USERNAME!"=="" (
    echo   • Send alerts only if manual action is needed
) else (
    echo   • Send alerts when manual renewal is needed
    echo   • Set INSTA_USERNAME and INSTA_PASSWORD for automatic renewal
)
echo.
echo LOGS:
echo   • Check: %PROJECT_DIR%auto_renew_log.txt for run logs
echo   • Alert: Look for RENEWAL_ALERT.txt when renewal is needed
echo.
echo TEST THE SETUP:
echo   • Run manually: python auto_renew_session.py
echo   • Or wait for 2:00 AM tomorrow for automatic run
echo.
echo MANUAL CONTROL:
echo   • View tasks: tasklist /fo list /v (includes task name)
echo   • Edit task: Open Task Scheduler → Tasks → ReelForge
echo   • Disable: Right-click task → Disable
echo   • Remove: schtasks /delete "ReelForge\Session Auto-Renewal" /f
echo.
echo ================================================================================
echo.
pause
