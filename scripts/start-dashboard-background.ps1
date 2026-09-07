# Start Project Brain API in background (no console window)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  Write-Host "Run scripts\install-and-demo.ps1 first." -ForegroundColor Red
  exit 1
}

$Port = if ($env:BRAIN_API_PORT) { $env:BRAIN_API_PORT } else { "18787" }
$DataDir = Join-Path $Root ".data"
$LogDir = Join-Path $DataDir "logs"
$PidFile = Join-Path $DataDir "brain-api.pid"
$LogFile = Join-Path $LogDir "brain-api.log"
$ErrFile = Join-Path $LogDir "brain-api.err.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-BrainApiUp {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 2
    return $r.StatusCode -eq 200
  } catch {
    return $false
  }
}

if (Test-Path $PidFile) {
  $oldPid = (Get-Content $PidFile -Raw).Trim()
  if ($oldPid -match '^\d+$') {
    $proc = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
    if ($proc -and (Test-BrainApiUp)) {
      Write-Host "Already running PID $oldPid"
      Write-Host "Dashboard: http://127.0.0.1:$Port/dashboard"
      exit 0
    }
    if ($proc) { Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue }
  }
}

$env:PYTHONPATH = Join-Path $Root "src"

$p = Start-Process `
  -FilePath $Python `
  -ArgumentList @(
    "-m", "uvicorn", "brain_api.app:app",
    "--host", "127.0.0.1", "--port", $Port, "--log-level", "info"
  ) `
  -WorkingDirectory $Root `
  -WindowStyle Hidden `
  -PassThru `
  -RedirectStandardOutput $LogFile `
  -RedirectStandardError $ErrFile

Set-Content -Path $PidFile -Value $p.Id -Encoding ascii

Start-Sleep -Seconds 3
if (Test-BrainApiUp) {
  Write-Host "Started in background PID $($p.Id) (no console window)"
  Write-Host "Dashboard: http://127.0.0.1:$Port/dashboard"
  Write-Host "Log: $LogFile"
  Write-Host "Stop: scripts\stop-dashboard.ps1"
} else {
  Write-Host "Start failed. Check $LogFile and $ErrFile" -ForegroundColor Yellow
  exit 1
}
