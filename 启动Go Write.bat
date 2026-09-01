@echo off
title Go Write

set "ROOT=%~dp0"
set "APP_DIR="
for /d %%D in ("%ROOT%07_*") do (
    if exist "%%~fD\desktop\main.py" set "APP_DIR=%%~fD"
)

echo ========================================
echo   Go Write
echo ========================================
echo.

if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo Go Write runtime is missing.
    echo.
    echo Required: %ROOT%.venv\Scripts\python.exe
    pause
    exit /b 1
)

if not defined APP_DIR (
    echo Go Write application directory was not found below: %ROOT%
    pause
    exit /b 1
)

REM Check the frontend build using desktop/main.py's runtime manifest contract.
cd /d "%APP_DIR%"
if errorlevel 1 (
    echo Cannot enter application directory: %APP_DIR%
    pause
    exit /b 1
)

"%ROOT%.venv\Scripts\python.exe" desktop\main.py --check-runtime-build
if errorlevel 1 (
    echo Building the Go Write frontend...
    echo.
    cd /d "%APP_DIR%\ui"
    if errorlevel 1 (
        echo Cannot enter frontend directory: %APP_DIR%\ui
        pause
        exit /b 1
    )
    call npm run build
    if errorlevel 1 (
        echo.
        echo Go Write frontend build failed. Check Node.js and npm.
        pause
        exit /b 1
    )
    echo.
    echo Frontend build completed.
    echo.

    cd /d "%APP_DIR%"
    "%ROOT%.venv\Scripts\python.exe" desktop\main.py --check-runtime-build
    if errorlevel 1 (
        echo Runtime manifest is still stale after the build. Startup stopped.
        pause
        exit /b 1
    )
)

REM Start the desktop application. Python owns the detailed startup diagnostics.
cd /d "%APP_DIR%"
if errorlevel 1 (
    echo Cannot enter application directory: %APP_DIR%
    pause
    exit /b 1
)

"%ROOT%.venv\Scripts\python.exe" desktop\main.py
if errorlevel 1 (
    echo.
    echo Go Write failed to start. Detailed startup log:
    if defined AI_WRITE_CONFIG_DIR (
        echo %AI_WRITE_CONFIG_DIR%\logs\desktop-startup.log
    ) else (
        echo %USERPROFILE%\.ai-write\logs\desktop-startup.log
    )
    echo Keep this window open and inspect that log for the exact failure stage.
    pause
    exit /b 1
)
