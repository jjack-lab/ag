@echo off
rem ============================================
rem  Codex quota watcher launcher
rem  Detects quota/rate-limit errors in local
rem  Codex session logs, auto WIP-commits and
rem  records the interruption in HANDOFF.md.
rem  Start this BEFORE you begin daily work.
rem ============================================
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    pause
    exit /b 1
)
python scripts\watch_quota.py %*
pause
