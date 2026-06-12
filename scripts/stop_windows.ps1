# FinAlly stop script (Windows / PowerShell)
# Stops the FastAPI process listening on port 8000.
# Leaves db/finally.db untouched.

$ErrorActionPreference = "SilentlyContinue"

$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen
if (-not $conns) {
    Write-Host "[FinAlly] No process listening on port 8000."
    return
}

$pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $pids) {
    Write-Host "[FinAlly] Stopping process $procId ..."
    Stop-Process -Id $procId -Force
}
Write-Host "[FinAlly] Stopped."
