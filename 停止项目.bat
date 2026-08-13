@echo off
setlocal
cd /d "%~dp0"

echo Stopping AgriNebula...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_delivery.ps1"
if errorlevel 1 (
    echo.
    echo [ERROR] Stop failed. Review the message above.
    pause
    exit /b 1
)

echo.
echo AgriNebula services are stopped.
exit /b 0
