# FinAlly start script (Windows / PowerShell)
# Builds the frontend, syncs the backend, and launches FastAPI on port 8000.
# Pass -NoBrowser to skip opening the browser.

param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$backend = Join-Path $root "backend"

Write-Host "[FinAlly] Building frontend..."
Push-Location $frontend
npm install
npm run build
Pop-Location

Write-Host "[FinAlly] Syncing backend..."
Push-Location $backend
uv sync
Pop-Location

Write-Host "[FinAlly] Starting FastAPI on http://127.0.0.1:8000 ..."
$server = Start-Process -PassThru -NoNewWindow -WorkingDirectory $backend `
    -FilePath "uv" `
    -ArgumentList "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"

if (-not $NoBrowser) {
    # Open the browser only once the server answers, so the first page load works.
    for ($i = 0; $i -lt 60; $i++) {
        try {
            if ((Invoke-WebRequest "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { break }
        } catch { Start-Sleep -Seconds 1 }
    }
    Start-Process "http://127.0.0.1:8000"
}

Wait-Process -Id $server.Id
