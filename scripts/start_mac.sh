#!/usr/bin/env bash
# FinAlly start script (macOS / Linux)
# Builds the frontend, syncs the backend, and launches FastAPI on port 8000.
# Pass --no-browser to skip opening the browser.

set -euo pipefail

NO_BROWSER=false
for arg in "$@"; do
    if [ "$arg" = "--no-browser" ]; then
        NO_BROWSER=true
    fi
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"
BACKEND="$ROOT/backend"

echo "[FinAlly] Building frontend..."
cd "$FRONTEND"
npm install
npm run build

echo "[FinAlly] Syncing backend..."
cd "$BACKEND"
uv sync

if [ "$NO_BROWSER" = false ]; then
    open "http://localhost:8000" 2>/dev/null || xdg-open "http://localhost:8000" 2>/dev/null || true
fi

echo "[FinAlly] Starting FastAPI on http://localhost:8000 ..."
cd "$BACKEND"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
