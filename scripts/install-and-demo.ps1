# Run on Windows PowerShell from repo root
$ErrorActionPreference = "Stop"
$Root = Join-Path $PSScriptRoot ".."
Set-Location $Root

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
  if (-not $pyLauncher) {
    Write-Host "Need Python 3.11 (install from python.org or: py -3.11)" -ForegroundColor Red
    exit 1
  }
  & py -3.11 -m venv .venv
  if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "venv create failed. Use: py -3.11 -m venv .venv" -ForegroundColor Red
    exit 1
  }
}

.\.venv\Scripts\python -m pip install -U pip -q
.\.venv\Scripts\python -m pip install -r requirements.txt -q

$env:PYTHONPATH = "src"
.\.venv\Scripts\python scripts\seed_fixtures.py
.\.venv\Scripts\python -m pytest tests/ -q
if ($LASTEXITCODE -ne 0) {
  Write-Host "pytest failed — fix errors above before starting API/MCP." -ForegroundColor Red
  exit $LASTEXITCODE
}

Write-Host "`n=== Live demo (T1) ===" -ForegroundColor Cyan
.\.venv\Scripts\python scripts\demo_t1.py
if ($LASTEXITCODE -ne 0) {
  Write-Host "T1 demo failed." -ForegroundColor Red
  exit $LASTEXITCODE
}

Write-Host "`nInstall OK." -ForegroundColor Green
Write-Host "  Dashboard: .\scripts\start-dashboard-background.ps1  -> http://127.0.0.1:18787/dashboard"
Write-Host "  Verify:    .\scripts\verify-install.ps1"
Write-Host "  MCP:       see README.md (Cursor mcp.json)"
