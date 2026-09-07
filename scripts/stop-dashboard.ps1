# Stop background Brain API
$Root = Split-Path $PSScriptRoot -Parent
$PidFile = Join-Path $Root ".data\brain-api.pid"
$Port = if ($env:BRAIN_API_PORT) { $env:BRAIN_API_PORT } else { "18787" }

if (-not (Test-Path $PidFile)) {
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($conn) {
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped process on port $Port PID $($conn.OwningProcess)"
  } else {
    Write-Host "Service not running."
  }
  exit 0
}

$pidVal = (Get-Content $PidFile -Raw).Trim()
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
if ($pidVal -match '^\d+$') {
  Stop-Process -Id ([int]$pidVal) -Force -ErrorAction SilentlyContinue
  Write-Host "Stopped Brain API PID $pidVal"
}
