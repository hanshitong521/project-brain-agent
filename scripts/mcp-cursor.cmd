@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo project-brain: run scripts\install-and-demo.ps1 first >&2
  exit /b 1
)
set "PYTHONPATH=%CD%\src"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONIOENCODING=utf-8"
".venv\Scripts\python.exe" -u -m brain_mcp.server %*
