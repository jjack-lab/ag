@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo 正在停止星牧智控...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_delivery.ps1"
if errorlevel 1 (
    echo.
    echo [错误] 项目停止失败，请查看上方信息。
    pause
    exit /b 1
)

echo.
echo 项目服务已停止。
pause
exit /b 0
