# Quick health check after install (run from anywhere)
$ErrorActionPreference = "Stop"
$Root = Join-Path $PSScriptRoot ".."
Set-Location $Root

$fail = 0
function Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Bad($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red; $script:fail = 1 }

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Bad "No .venv — run: .\scripts\install-and-demo.ps1"
  exit 1
}
Ok "venv: $py"

$env:PYTHONPATH = Join-Path $Root "src"
& $py -c "import brain_mcp.server; import brain_api.app" 2>$null
if ($LASTEXITCODE -ne 0) {
  Bad "Python imports (brain_mcp / brain_api). Try: pip install -r requirements.txt"
} else {
  Ok "imports brain_mcp + brain_api"
}

$wrapper = Join-Path $Root "scripts\mcp-cursor.cmd"
if (-not (Test-Path $wrapper)) {
  Bad "missing scripts\mcp-cursor.cmd"
} else {
  $init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}'
  $out = $init | cmd /c "`"$wrapper`"" 2>&1
  if ($out -match '"serverInfo".*"project-brain"') { Ok "MCP wrapper (mcp-cursor.cmd) initialize" }
  else { Bad "MCP wrapper failed: $out" }
}

$port = if ($env:BRAIN_API_PORT) { $env:BRAIN_API_PORT } else { "18787" }
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 2
  if ($r.StatusCode -eq 200) { Ok "API http://127.0.0.1:$port/health" }
  else { Bad "API returned $($r.StatusCode)" }
} catch {
  Bad "API not running on port $port — run .\scripts\start-dashboard-background.ps1"
}

if ($fail) { exit 1 }
Write-Host "`nAll checks passed." -ForegroundColor Cyan
