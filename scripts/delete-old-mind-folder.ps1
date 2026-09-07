# Delete empty leftover e:\workA\A-skill\project-brain-mind after merge.
# Run AFTER switching Cursor workspace to project-brain-agent (close old folder).
$path = "e:\workA\A-skill\project-brain-mind"
if (-not (Test-Path $path)) {
  Write-Host "Already gone: $path"
  exit 0
}
$items = @(Get-ChildItem -Path $path -Force -ErrorAction SilentlyContinue)
if ($items.Count -gt 0) {
  Write-Host "Folder not empty ($($items.Count) items). Merge may be incomplete; abort."
  exit 1
}
try {
  Remove-Item -LiteralPath $path -Force -ErrorAction Stop
  Write-Host "Deleted: $path"
  exit 0
} catch {
  Write-Host "Still locked (usually Cursor has old workspace open)."
  Write-Host "1) File -> Open Folder -> project-brain-agent"
  Write-Host "2) Run this script again"
  Write-Host $_.Exception.Message
  exit 1
}
