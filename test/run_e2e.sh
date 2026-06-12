#!/usr/bin/env bash
# FinAlly E2E runner (macOS / Linux)
# Builds the app, starts the backend with LLM_MOCK=true, runs Playwright
# against http://localhost:8000, then tears the backend down.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"
BACKEND="$ROOT/backend"
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[e2e] Building frontend..."
cd "$FRONTEND"
npm install
npm run build

echo "[e2e] Syncing backend..."
cd "$BACKEND"
uv sync

echo "[e2e] Installing Playwright deps..."
cd "$TEST_DIR"
npm install
npx playwright install --with-deps chromium

echo "[e2e] Starting backend (LLM_MOCK=true)..."
cd "$BACKEND"
LLM_MOCK=true uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cleanup() {
    echo "[e2e] Stopping backend..."
    kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "[e2e] Waiting for backend health..."
ready=false
for _ in $(seq 1 60); do
    if curl -sf "http://127.0.0.1:8000/api/health" >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done
if [ "$ready" = false ]; then
    echo "[e2e] Backend did not become healthy in time" >&2
    exit 1
fi

echo "[e2e] Running Playwright suite..."
cd "$TEST_DIR"
npx playwright test
