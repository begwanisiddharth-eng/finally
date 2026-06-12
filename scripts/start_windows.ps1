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

if (-not $NoBrowser) {
    Start-Process "http://localhost:8000"
}

Write-Host "[FinAlly] Starting FastAPI on http://localhost:8000 ..."
Push-Location $backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
Pop-Location
