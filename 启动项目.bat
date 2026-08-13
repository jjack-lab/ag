@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "AGRINEBULA_PYTHON=F:\deepl\anaconda1\envs\pytorch\python.exe"
set "AGRINEBULA_WEB_URL=http://127.0.0.1:5173"

if not exist "%AGRINEBULA_PYTHON%" (
    echo [错误] 未找到项目 Python 环境：
    echo %AGRINEBULA_PYTHON%
    echo 请安装或修复该环境后重试。
    pause
    exit /b 1
)

echo 正在启动星牧智控，请稍候...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_delivery.ps1"
if errorlevel 1 (
    echo.
    echo [错误] 项目启动失败，请查看上方信息。
    pause
    exit /b 1
)

echo.
echo 项目已启动：%AGRINEBULA_WEB_URL%
echo 正在打开浏览器...
start "" "%AGRINEBULA_WEB_URL%"
exit /b 0
