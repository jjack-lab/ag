@echo off
setlocal
cd /d "%~dp0"

set "AGRINEBULA_PYTHON=F:\deepl\anaconda1\envs\pytorch\python.exe"
set "AGRINEBULA_WEB_URL=http://127.0.0.1:5173"

if not exist "%AGRINEBULA_PYTHON%" (
    echo [ERROR] Project Python was not found:
    echo %AGRINEBULA_PYTHON%
    echo Repair this environment and try again.
    pause
    exit /b 1
)

echo Starting AgriNebula. Please wait...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_delivery.ps1"
if errorlevel 1 (
    echo.
    echo [ERROR] Startup failed. Review the message above.
    pause
    exit /b 1
)

echo.
echo AgriNebula is ready: %AGRINEBULA_WEB_URL%
echo Opening the web console...
start "" "%AGRINEBULA_WEB_URL%"
exit /b 0
