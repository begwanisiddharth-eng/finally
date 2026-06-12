# FinAlly E2E runner (Windows / PowerShell)
# Builds the app, starts the backend with LLM_MOCK=true, runs Playwright
# against http://localhost:8000, then tears the backend down.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$backend = Join-Path $root "backend"
$testDir = $PSScriptRoot

Write-Host "[e2e] Building frontend..."
Push-Location $frontend
npm install
npm run build
Pop-Location

Write-Host "[e2e] Syncing backend..."
Push-Location $backend
uv sync
Pop-Location

Write-Host "[e2e] Installing Playwright deps..."
Push-Location $testDir
npm install
npx playwright install --with-deps chromium
Pop-Location

Write-Host "[e2e] Starting backend (LLM_MOCK=true)..."
$env:LLM_MOCK = "true"
$backendProc = Start-Process -PassThru -WorkingDirectory $backend `
    -FilePath "uv" `
    -ArgumentList "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"

try {
    Write-Host "[e2e] Waiting for backend health..."
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw "Backend did not become healthy in time" }

    Write-Host "[e2e] Running Playwright suite..."
    Push-Location $testDir
    npx playwright test
    $exit = $LASTEXITCODE
    Pop-Location
}
finally {
    Write-Host "[e2e] Stopping backend..."
    if ($backendProc -and -not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
    # Also clean up any child uvicorn process holding the port.
    Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

exit $exit
