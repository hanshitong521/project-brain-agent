@echo off
REM 后台启动（无黑框，推荐）。本窗口会立即关闭。
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dashboard-background.ps1"
if errorlevel 1 pause
exit /b 0
