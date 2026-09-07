$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONPATH = Join-Path $PWD "src"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "请先运行: .\scripts\install-and-demo.ps1" -ForegroundColor Red
  exit 1
}

$port = if ($env:BRAIN_API_PORT) { $env:BRAIN_API_PORT } else { "18787" }
Write-Host ""
Write-Host "看板地址: http://127.0.0.1:$port/dashboard" -ForegroundColor Cyan
Write-Host "健康检查: http://127.0.0.1:$port/health" -ForegroundColor DarkGray
Write-Host "按 Ctrl+C 停止" -ForegroundColor DarkGray
Write-Host ""

& .\.venv\Scripts\python.exe -m uvicorn brain_api.app:app --host 127.0.0.1 --port $port
