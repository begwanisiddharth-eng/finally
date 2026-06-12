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

echo "[FinAlly] Starting FastAPI on http://127.0.0.1:8000 ..."
cd "$BACKEND"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

if [ "$NO_BROWSER" = false ]; then
    # Open the browser only once the server answers, so the first page load works.
    for _ in $(seq 1 60); do
        if curl -sf "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then break; fi
        sleep 1
    done
    open "http://127.0.0.1:8000" 2>/dev/null || xdg-open "http://127.0.0.1:8000" 2>/dev/null || true
fi

wait "$SERVER_PID"
